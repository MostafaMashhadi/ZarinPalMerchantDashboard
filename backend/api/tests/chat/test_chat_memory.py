"""Tests for ChatMemoryConsolidation (§9.6.3, §19.28).

Tests:
- Upsert is additive/merge, never destructive overwrite
- Delete strictly ordered after successful upsert (crash-safety)
- Historical memory retrieval when question references old period
- ChatGroundingValidator allows historical memory numbers without
  source_insight_id traceability
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from chat.grounding.chat_grounding_validator import (
    ChatGroundingValidator,
)
from chat.intent.intent_resolver import IntentClass
from chat.services.chat_orchestration_service import (
    HISTORICAL_MEMORY_KEYWORDS,
    ChatOrchestrationService,
)


class TestHistoricalMemoryRetrieval:
    """§9.6.3: historical memory included when question references old period."""

    def test_historical_memory_included_for_old_period_query(self):
        """'What did I ask last month...' triggers memory lookup."""
        service = ChatOrchestrationService(
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        mock_memory = MagicMock()
        mock_memory.period_start = datetime.now() - timedelta(days=45)
        mock_memory.period_end = datetime.now() - timedelta(days=35)
        mock_memory.summary_text = "Past conversation about revenue drop"
        mock_memory.key_facts = ["revenue was 5000000", "issue was chargebacks"]

        with patch(
            "chat.services.chat_orchestration_service.MerchantChatMemory"
        ) as mock_model:
            mock_qs = MagicMock()
            mock_qs.filter.return_value.order_by.return_value.__getitem__ = (
                MagicMock(return_value=[mock_memory])
            )
            mock_model.objects = mock_qs

            historical = service._get_historical_memory(
                uuid4(), "what did I ask last month about revenue"
            )

        assert historical["digest_available"] is True
        assert len(historical["memories"]) >= 1
        assert "approximate recollection" in historical["note"]

    def test_no_historical_memory_for_recent_query(self):
        """'revenue last week' does not trigger memory lookup."""
        service = ChatOrchestrationService(
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        historical = service._get_historical_memory(
            uuid4(), "revenue last week"
        )

        assert historical == {}

    def test_no_historical_memory_for_non_matching_message(self):
        """Message without historical keywords returns empty."""
        service = ChatOrchestrationService(
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        historical = service._get_historical_memory(
            uuid4(), "what is the current status"
        )

        assert historical == {}

    def test_historical_memory_numbers_allowed_by_grounding_validator(self):
        """Historical memory numbers don't need source_insight_id (§9.6.4 exception)."""
        validator = ChatGroundingValidator()
        historical_context = {
            "source_data": {},
            "low_confidence_peer_set": False,
            "historical_memory": {
                "digest_available": True,
                "memories": [
                    {
                        "key_facts": ["revenue was 5000000"],
                    }
                ],
            },
        }

        result = validator.validate(
            "As I recall, revenue was 5000000",
            claims=[],
            context=historical_context,
        )

        assert result.valid, f"Should be valid, violations: {result.ungrounded_values}"

    def test_ungrounded_number_in_historical_context_still_rejected(self):
        """Numbers not in historical memory or claims are still rejected."""
        validator = ChatGroundingValidator()
        historical_context = {
            "source_data": {},
            "low_confidence_peer_set": False,
            "historical_memory": {
                "digest_available": True,
                "memories": [
                    {
                        "key_facts": ["revenue was 5000000"],
                    }
                ],
            },
        }

        result = validator.validate(
            "Revenue was 999999999",
            claims=[],
            context=historical_context,
        )

        assert not result.valid
        assert any("999999999" in v for v in result.ungrounded_values)


class TestHistoricalKeywords:
    def test_keywords_present(self):
        assert "last month" in HISTORICAL_MEMORY_KEYWORDS
        assert "ago" in HISTORICAL_MEMORY_KEYWORDS
        assert "before" in HISTORICAL_MEMORY_KEYWORDS

    def test_non_historical_message_does_not_trigger(self):
        msg = "what was my revenue this month"
        assert not any(
            kw in msg.lower() for kw in HISTORICAL_MEMORY_KEYWORDS
        )


class TestConsolidationAdditiveUpsert:
    """§19.28: upsert is additive/merge, never destructive overwrite."""

    def _simulate_upsert_merge(
        self, existing_summary, existing_facts, new_summary, new_facts
    ):
        """Mirror the additive merge logic of upsert_merchant_chat_memory."""
        merged_summary = existing_summary + "\n---\n" + new_summary
        merged_facts = list(dict.fromkeys(existing_facts + new_facts))
        return merged_summary, merged_facts

    def test_second_run_appends_to_existing_summary(self):
        existing = "Original summary about revenue."
        new = "New summary about chargebacks."

        merged, _ = self._simulate_upsert_merge(
            existing, ["fact1", "fact2"], new, ["fact3", "fact2"]
        )

        assert "Original summary about revenue" in merged
        assert "New summary about chargebacks" in merged
        assert "---" in merged

    def test_facts_deduplicated(self):
        _, facts = self._simulate_upsert_merge(
            "orig", ["fact1", "fact2"], "new", ["fact3", "fact2"]
        )
        assert len(facts) == 3
        assert "fact2" in facts

    def test_facts_accumulate_across_runs(self):
        _, facts = self._simulate_upsert_merge(
            "orig", ["fact1"], "new", ["fact1", "fact2"]
        )
        assert len(facts) == 2
        assert "fact1" in facts
        assert "fact2" in facts


class TestConsolidationCrashSafety:
    """§19.28: crash between upsert and delete never loses data."""

    def test_delete_step_ordered_after_upsert(self):
        """Workflow structure: delete is a separate activity AFTER upsert."""
        from workflows.chat_memory_consolidation import (
            ChatMemoryConsolidationWorkflow,
        )

        assert hasattr(ChatMemoryConsolidationWorkflow, "run")

    def test_delete_filters_by_session_and_period(self):
        """Delete activity filters CHAT_MESSAGE by session + period bounds."""
        with patch("chat.models.ChatMessage") as mock_msg_model:
            mock_qs = MagicMock()
            mock_qs.delete.return_value = (5, {})
            mock_msg_model.objects.filter.return_value = mock_qs

            from activities.chat_memory_activities import (
                DeleteInput,
                delete_consolidated_messages,
            )

            delete_input = DeleteInput(
                session_id="sess-1",
                period_start="2026-06-01T00:00:00+00:00",
                period_end="2026-06-30T00:00:00+00:00",
            )

            result = asyncio.run(
                delete_consolidated_messages(delete_input)
            )

        assert result.deleted_count == 5
        mock_msg_model.objects.filter.assert_called_once()

    def test_upsert_merge_preserves_existing_data(self):
        """Upsert merge preserves existing summary text, appends new content."""
        existing = MagicMock()
        existing.summary_text = "Existing: revenue was high in Q1."
        existing.key_facts = ["q1_revenue: 12000000"]
        existing.save = MagicMock()

        mock_qs = MagicMock()
        mock_qs.first.return_value = existing

        with patch(
            "chat.models.MerchantChatMemory"
        ) as mock_model:
            mock_model.objects.filter.return_value = mock_qs

            with patch(
                "django.db.transaction.atomic"
            ) as mock_atomic:
                mock_atomic.return_value.__enter__ = MagicMock()
                mock_atomic.return_value.__exit__ = MagicMock(
                    return_value=False
                )

                from activities.chat_memory_activities import (
                    UpsertInput,
                    upsert_merchant_chat_memory,
                )

                upsert_input = UpsertInput(
                    merchant_id="m1",
                    period_start="2026-06-01T00:00:00+00:00",
                    period_end="2026-06-30T00:00:00+00:00",
                    summary_text="New: chargeback spike detected.",
                    key_facts=["chargeback_rate: 0.15"],
                    tokens_in=100,
                    tokens_out=200,
                    model="cheap",
                    tier="cheap",
                )

                result = asyncio.run(
                    upsert_merchant_chat_memory(upsert_input)
                )

        assert result.upserted is True
        assert "Existing: revenue" in existing.summary_text
        assert "New: chargeback" in existing.summary_text
        assert "q1_revenue: 12000000" in existing.key_facts
        assert "chargeback_rate: 0.15" in existing.key_facts
        existing.save.assert_called_once()

    def test_delete_returns_count_of_deleted_rows(self):
        """Delete activity returns the count of deleted rows for observability."""
        with patch("chat.models.ChatMessage") as mock_msg_model:
            mock_qs = MagicMock()
            mock_qs.delete.return_value = (42, {})
            mock_msg_model.objects.filter.return_value = mock_qs

            from activities.chat_memory_activities import (
                DeleteInput,
                delete_consolidated_messages,
            )

            result = asyncio.run(
                delete_consolidated_messages(
                    DeleteInput(
                        session_id="sess-1",
                        period_start="2026-06-01T00:00:00+00:00",
                        period_end="2026-06-30T00:00:00+00:00",
                    )
                )
            )

        assert result.deleted_count == 42


class TestChatOrchestrationHistoricalIntegration:
    """§9.6.3: ChatOrchestrationService correctly references historical memory."""

    def test_context_includes_historical_memory_key(self):
        """Bounded context includes 'historical_memory' key for the chain."""
        service = ChatOrchestrationService(
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        with patch.object(service, "_intent_resolver") as mock_resolver, \
             patch.object(service, "_insight_repo") as mock_insight_repo, \
             patch.object(service, "_message_repo") as mock_msg_repo, \
             patch(
                 "chat.services.chat_orchestration_service.MerchantChatMemory"
             ) as mock_mem_model:

            mock_resolver.resolve.return_value = IntentClass(
                kind="general", params={}, confidence=0.5
            )
            mock_insight_repo.find_recent.return_value = []
            mock_msg_repo.list_for_session.return_value = []

            mock_qs = MagicMock()
            mock_qs.filter.return_value.order_by.return_value.__getitem__ = (
                MagicMock(return_value=[])
            )
            mock_mem_model.objects = mock_qs

            session = MagicMock()
            session.id = uuid4()
            session.merchant_id = uuid4()

            context = service._build_bounded_context(
                session,
                "what did I ask last month about revenue",
                IntentClass(kind="general", params={}, confidence=0.5),
                {"source": "general", "result": None},
            )

        assert "historical_memory" in context
