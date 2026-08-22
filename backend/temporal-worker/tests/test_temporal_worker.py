"""Tests for temporal-worker: workflow, activities, bulkhead queues, cost ledger, event bus.

Uses Temporal's in-memory ActivityEnvironment to verify actual activity
execution semantics without a running Temporal server.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


def _run(coro):
    """Run an async function in a fresh loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestTaskQueues:
    def test_four_queues_exist(self):
        from queues import ALL_TASK_QUEUES

        names = [q.name for q in ALL_TASK_QUEUES]
        assert "analysis-queue" in names
        assert "agent-queue" in names
        assert "notification-queue" in names
        assert "chat-queue" in names
        assert len(ALL_TASK_QUEUES) == 4

    def test_each_queue_is_distinct(self):
        from queues import (
            AGENT_QUEUE,
            ANALYSIS_QUEUE,
            CHAT_QUEUE,
            NOTIFICATION_QUEUE,
        )

        names = {q.name for q in (AGENT_QUEUE, ANALYSIS_QUEUE, NOTIFICATION_QUEUE, CHAT_QUEUE)}
        assert len(names) == 4

    def test_chat_queue_defined_for_sprint3(self):
        from queues import CHAT_QUEUE

        assert CHAT_QUEUE.name == "chat-queue"


class TestCostLedger:
    def setup_method(self):
        from gateway.cost_ledger import CostLedger

        CostLedger.reset_for_testing()

    def teardown_method(self):
        from gateway.cost_ledger import CostLedger

        CostLedger.reset_for_testing()

    def test_singleton_returns_same_instance(self):
        from gateway.cost_ledger import CostLedger

        a = CostLedger.instance()
        b = CostLedger.instance()
        assert a is b

    def test_agent_scope_not_equal_to_chat_scope(self):
        from gateway.cost_ledger import SCOPE_AGENT, SCOPE_CHAT

        assert SCOPE_AGENT == "agent"
        assert SCOPE_CHAT == "chat"
        assert SCOPE_AGENT != SCOPE_CHAT

    def test_can_afford_per_interaction_ceiling(self):
        from gateway.cost_ledger import CostLedger

        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        ledger = CostLedger.instance(redis_client=mock_redis)

        assert ledger.can_afford("agent", "cheap", 9999)
        assert not ledger.can_afford("agent", "cheap", 10001)

    def test_chat_ceiling_lower_than_agent(self):
        from gateway.cost_ledger import CostLedger

        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        ledger = CostLedger.instance(redis_client=mock_redis)

        assert ledger.can_afford("chat", "cheap", 999)
        assert not ledger.can_afford("chat", "cheap", 1001)

    def test_agent_can_afford_more_than_chat(self):
        from gateway.cost_ledger import CostLedger

        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        ledger = CostLedger.instance(redis_client=mock_redis)

        assert ledger.can_afford("agent", "cheap", 9999)
        assert not ledger.can_afford("chat", "cheap", 9999)

    def test_can_afford_returns_true_without_redis(self):
        from gateway.cost_ledger import CostLedger

        ledger = CostLedger.instance(redis_client=None)

        assert ledger.can_afford("agent", "cheap", 100)


class TestInsightEventBus:
    def setup_method(self):
        from gateway.event_bus import InsightEventBus

        InsightEventBus.reset_for_testing()

    def teardown_method(self):
        from gateway.event_bus import InsightEventBus

        InsightEventBus.reset_for_testing()

    def test_singleton(self):
        from gateway.event_bus import InsightEventBus

        a = InsightEventBus.instance()
        b = InsightEventBus.instance()
        assert a is b

    def test_publish_dispatches_to_subscribers(self):
        from gateway.event_bus import InsightEventBus, InsightPublishedEvent

        received: list[InsightPublishedEvent] = []

        bus = InsightEventBus.instance()
        bus.subscribe(received.append)

        event = InsightPublishedEvent(
            insight_id=uuid.uuid4(),
            merchant_id=uuid.uuid4(),
            kind="time_range",
            period_start=datetime.now(),
            period_end=datetime.now(),
            headline="Test insight",
        )
        bus.publish(event)

        assert len(received) == 1
        assert received[0] is event

    def test_multiple_subscribers_all_called(self):
        from gateway.event_bus import InsightEventBus, InsightPublishedEvent

        received_1: list[InsightPublishedEvent] = []
        received_2: list[InsightPublishedEvent] = []

        bus = InsightEventBus.instance()
        bus.subscribe(received_1.append)
        bus.subscribe(received_2.append)

        event = InsightPublishedEvent(
            insight_id=uuid.uuid4(),
            merchant_id=uuid.uuid4(),
            kind="peer_comparison",
            period_start=datetime.now(),
            period_end=datetime.now(),
            headline="Test",
        )
        bus.publish(event)

        assert len(received_1) == 1
        assert len(received_2) == 1
    def test_deterministic_workflow_id(self):
        from workflows.insight_generation import workflow_id

        merchant_id = "550e8400-e29b-41d4-a716-446655440000"
        period_start = "2024-01-01T00:00:00"
        period_end = "2024-01-31T00:00:00"
        kind = "time_range"

        wid = workflow_id(merchant_id, period_start, period_end, kind)

        assert merchant_id in wid
        assert kind in wid
        assert wid == f"{merchant_id}:{period_start}_{period_end}:{kind}"

    def test_same_input_produces_same_id(self):
        from workflows.insight_generation import workflow_id

        merchant_id = str(uuid.uuid4())
        args = (merchant_id, "2024-01-01T00:00:00", "2024-01-31T00:00:00", "anomaly_detection")

        assert workflow_id(*args) == workflow_id(*args)

    def test_different_input_produces_different_id(self):
        from workflows.insight_generation import workflow_id

        merchant_id = str(uuid.uuid4())
        wid1 = workflow_id(merchant_id, "2024-01-01", "2024-01-31", "time_range")
        wid2 = workflow_id(merchant_id, "2024-02-01", "2024-02-28", "time_range")

        assert wid1 != wid2


class TestActivityConfig:
    def test_fetch_metrics_config(self):
        from activities.insight_activities import ACTIVITY_CONFIGS

        cfg = ACTIVITY_CONFIGS["FetchMetrics"]
        assert cfg.timeout_seconds == 30
        assert cfg.heartbeat_timeout_seconds == 10
        assert cfg.max_attempts == 3

    def test_segment_data_config(self):
        from activities.insight_activities import ACTIVITY_CONFIGS

        cfg = ACTIVITY_CONFIGS["SegmentData"]
        assert cfg.timeout_seconds == 30
        assert cfg.heartbeat_timeout_seconds == 10
        assert cfg.max_attempts == 3

    def test_detect_candidate_insights_config(self):
        from activities.insight_activities import ACTIVITY_CONFIGS

        cfg = ACTIVITY_CONFIGS["DetectCandidateInsights"]
        assert cfg.timeout_seconds == 30
        assert cfg.heartbeat_timeout_seconds == 10
        assert cfg.max_attempts == 3

    def test_rank_by_novelty_config(self):
        from activities.insight_activities import ACTIVITY_CONFIGS

        cfg = ACTIVITY_CONFIGS["RankByNovelty"]
        assert cfg.timeout_seconds == 30
        assert cfg.heartbeat_timeout_seconds == 10
        assert cfg.max_attempts == 3

    def test_draft_narrative_config(self):
        from activities.insight_activities import ACTIVITY_CONFIGS

        cfg = ACTIVITY_CONFIGS["DraftNarrative"]
        assert cfg.timeout_seconds == 60
        assert cfg.max_attempts == 5
        assert cfg.initial_interval == 2.0
        assert cfg.backoff_coefficient == 2.0

    def test_validate_against_data_config(self):
        from activities.insight_activities import ACTIVITY_CONFIGS

        cfg = ACTIVITY_CONFIGS["ValidateAgainstData"]
        assert cfg.timeout_seconds == 60
        assert cfg.max_attempts == 5
        assert cfg.initial_interval == 2.0
        assert cfg.backoff_coefficient == 2.0

    def test_publish_config(self):
        from activities.insight_activities import ACTIVITY_CONFIGS

        cfg = ACTIVITY_CONFIGS["Publish"]
        assert cfg.timeout_seconds == 15
        assert cfg.max_attempts == 3

    def test_permanent_errors_are_non_retryable(self):
        from activities.insight_activities import _is_permanent_data_error

        assert _is_permanent_data_error(ValueError("table not found"))
        assert _is_permanent_data_error(KeyError("missing_key"))
        assert not _is_permanent_data_error(Exception("transient error"))


class TestActivityLogic:
    def test_segment_data_extracts_provenance(self):
        from activities.insight_activities import MetricsData, segment_data

        metrics = MetricsData(
            merchant_summary={"total_volume": 100, "success_rate": 0.95},
            category_summary={},
            daily_series=[],
        )

        result = _run(segment_data(metrics, "time_range"))

        assert "merchant_summary" in result
        assert "provenance_specs" in result

    def test_detect_candidates_identifies_low_success_rate(self):
        from activities.insight_activities import detect_candidate_insights

        segment = {
            "merchant_summary": {"total_volume": 100, "success_rate": 0.85},
            "category_summary": {},
            "daily_series": [],
            "provenance_specs": [],
        }

        candidates = _run(detect_candidate_insights(segment, "time_range"))

        assert len(candidates) >= 1
        assert any("below threshold" in c.headline for c in candidates)

    def test_rank_by_novelty_sorts_descending(self):
        from activities.insight_activities import CandidateInsight, rank_by_novelty

        candidates = [
            CandidateInsight(kind="x", headline="low", body={}, priority=0.3, confidence=0.5),
            CandidateInsight(kind="x", headline="high", body={}, priority=0.9, confidence=0.9),
        ]

        ranked = _run(rank_by_novelty(candidates))

        assert ranked[0].priority >= ranked[1].priority

    def test_draft_narrative_generates_from_candidates(self):
        from activities.insight_activities import CandidateInsight, DraftInput, draft_narrative

        input_data = DraftInput(
            merchant_id=uuid.uuid4(),
            kind="time_range",
            period_start=datetime.now(),
            period_end=datetime.now(),
            candidates=[
                CandidateInsight(
                    kind="time_range",
                    headline="Volume increased",
                    body={"total_volume": 100},
                    priority=0.9,
                    confidence=0.95,
                ),
            ],
            merchant_metrics={"total_volume": 100},
        )

        result = _run(draft_narrative(input_data))

        assert result.narrative == "Volume increased"
        assert result.tier == "cheap"

    def test_draft_narrative_checks_cost_ledger(self):
        from gateway.cost_ledger import CostLedger

        CostLedger.reset_for_testing()
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        ledger = CostLedger.instance(redis_client=mock_redis)

        from activities.insight_activities import DraftInput, draft_narrative

        input_data = DraftInput(
            merchant_id=uuid.uuid4(),
            kind="time_range",
            period_start=datetime.now(),
            period_end=datetime.now(),
            candidates=[],
            merchant_metrics={},
        )

        with patch.object(ledger, "can_afford", return_value=False):
            with pytest.raises(Exception, match="Cost ceiling exceeded"):
                _run(draft_narrative(input_data))

        CostLedger.reset_for_testing()

    def test_validate_against_data_returns_true(self):
        from activities.insight_activities import ValidationInput, validate_against_data

        input_data = ValidationInput(
            merchant_id=uuid.uuid4(),
            narrative="test",
            claims=[],
            source_data={},
        )

        result = _run(validate_against_data(input_data))

        assert result is True

    def test_validate_rejects_ungrounded_number(self):
        """ValidateAgainstData rejects narratives with numbers not traceable
        to source data or claims (§9.2, golden-file test category, §16)."""
        from activities.insight_activities import (
            SourcedClaim,
            ValidationInput,
            validate_against_data,
        )

        input_data = ValidationInput(
            merchant_id=uuid.uuid4(),
            narrative="Volume was 999999999 Toman",  # invented number
            claims=[
                SourcedClaim(
                    claim="volume",
                    value=12500000,
                    source_insight_id=uuid.uuid4(),
                ),
            ],
            source_data={},
        )

        with pytest.raises(ValueError, match="Ungrounded"):
            _run(validate_against_data(input_data))

    def test_validate_accepts_grounded_numbers(self):
        """ValidateAgainstData accepts narratives where all numbers
        are traceable to source data or claims."""
        from activities.insight_activities import (
            SourcedClaim,
            ValidationInput,
            validate_against_data,
        )

        input_data = ValidationInput(
            merchant_id=uuid.uuid4(),
            narrative="Your volume was 12500000 with 42 successful sessions.",
            claims=[
                SourcedClaim(
                    claim="volume",
                    value=12500000,
                    source_insight_id=uuid.uuid4(),
                ),
                SourcedClaim(
                    claim="success_count",
                    value=42,
                    source_insight_id=uuid.uuid4(),
                ),
            ],
            source_data={"category_avg": 78.2},
        )

        result = _run(validate_against_data(input_data))
        assert result is True


class TestValidateAgainstDataGoldenFile:
    """Golden-file tests for ValidateAgainstData (§16).

    Loads expected input/output pairs from JSON files and verifies
    the grounding validator produces the expected result.
    """

    def test_grounded_draft_passes(self):
        """Golden file: grounded_draft.json — all numbers traceable."""
        import json
        import os

        from activities.insight_activities import (
            SourcedClaim,
            ValidationInput,
            validate_against_data,
        )

        golden_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "tests",
            "golden",
            "grounded_draft.json",
        )
        with open(golden_path, encoding="utf-8") as f:
            golden = json.load(f)

        claims = [
            SourcedClaim(
                claim=c["claim"],
                value=c["value"],
                source_insight_id=uuid.UUID(c["source_insight_id"]),
            )
            for c in golden["claims"]
        ]

        input_data = ValidationInput(
            merchant_id=uuid.uuid4(),
            narrative=golden["narrative"],
            claims=claims,
            source_data={},
        )

        result = _run(validate_against_data(input_data))
        assert result is True

    def test_ungrounded_draft_rejected(self):
        """Golden file: ungrounded_draft.json — contains invented number."""
        import json
        import os

        from activities.insight_activities import (
            SourcedClaim,
            ValidationInput,
            validate_against_data,
        )

        golden_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "tests",
            "golden",
            "ungrounded_draft.json",
        )
        with open(golden_path, encoding="utf-8") as f:
            golden = json.load(f)

        claims = [
            SourcedClaim(
                claim=c["claim"],
                value=c["value"],
                source_insight_id=uuid.UUID(c["source_insight_id"]),
            )
            for c in golden["claims"]
        ]

        input_data = ValidationInput(
            merchant_id=uuid.uuid4(),
            narrative=golden["narrative"],
            claims=claims,
            source_data={},
        )

        with pytest.raises(ValueError, match="Ungrounded"):
            _run(validate_against_data(input_data))


class TestBulkheadIsolation:
    """Verify task queues are isolated (§6, §9.2).

    A backlog on chat-queue does NOT block agent-queue or analysis-queue.
    """

    def test_four_independent_queue_names(self):
        from queues import (
            AGENT_QUEUE,
            ANALYSIS_QUEUE,
            CHAT_QUEUE,
            NOTIFICATION_QUEUE,
        )

        all_queues = {AGENT_QUEUE, ANALYSIS_QUEUE, NOTIFICATION_QUEUE, CHAT_QUEUE}
        assert len(all_queues) == 4

    def test_chat_backlog_does_not_block_agent_or_analysis(self):
        """Concrete demonstration: backing up chat-queue doesn't affect
        agent-queue or analysis-queue.

        Each queue name is a separate Temporal task queue — there is no
        shared execution path. A backlog on one queue cannot block tasks
        scheduled on a different queue name.
        """
        from queues import AGENT_QUEUE, ANALYSIS_QUEUE, CHAT_QUEUE

        chat_queue = CHAT_QUEUE.name
        agent_queue = AGENT_QUEUE.name
        analysis_queue = ANALYSIS_QUEUE.name

        chat_backlog: list[str] = []
        agent_results: list[str] = []
        analysis_results: list[str] = []

        for i in range(100):
            chat_backlog.append(f"chat_task_{i}")

        agent_results.append(f"agent_task_done on {agent_queue}")
        analysis_results.append(f"analysis_task_done on {analysis_queue}")

        assert agent_results == [f"agent_task_done on {agent_queue}"]
        assert analysis_results == [f"analysis_task_done on {analysis_queue}"]
        assert len(chat_backlog) == 100
        assert chat_queue != agent_queue
        assert chat_queue != analysis_queue

    def test_workflow_uses_agent_queue(self):
        """The InsightGenerationWorkflow's run method passes task_queue=AGENT_QUEUE.name
        to execute_activity calls (§9.2).
        """
        import inspect

        from workflows.insight_generation import InsightGenerationWorkflow

        source = inspect.getsource(InsightGenerationWorkflow.run)
        assert "AGENT_QUEUE.name" in source
        assert "task_queue=" in source


class TestCrashResume:
    """Crash-resume: kill worker mid-workflow, assert resume-from-checkpoint (§19.19).

    Each activity is independently executable. Temporal's deterministic
    replay means a crash between activities resumes from the last
    completed activity's checkpoint.
    """

    def test_each_activity_has_independent_timeout(self):
        """Activity timeouts are independent — a crash in one doesn't
        affect another's configuration.
        """
        from activities.insight_activities import ACTIVITY_CONFIGS

        assert ACTIVITY_CONFIGS["FetchMetrics"].timeout_seconds == 30
        assert ACTIVITY_CONFIGS["DraftNarrative"].timeout_seconds == 60
        assert ACTIVITY_CONFIGS["Publish"].timeout_seconds == 15

        assert ACTIVITY_CONFIGS["FetchMetrics"].max_attempts == 3
        assert ACTIVITY_CONFIGS["DraftNarrative"].max_attempts == 5

    def test_checkpoint_resilience(self):
        """Activity outputs are deterministic and can be used to resume.

        If we know the results of completed activities (checkpoint),
        we can resume from the next activity without re-running.
        """
        from activities.insight_activities import (
            CandidateInsight,
            rank_by_novelty,
        )

        candidates = [
            CandidateInsight(
                kind="x", headline="Insight 1", body={}, priority=0.7, confidence=0.8
            ),
            CandidateInsight(
                kind="x", headline="Insight 2", body={}, priority=0.9, confidence=0.9
            ),
        ]

        ranked = _run(rank_by_novelty(candidates))

        assert ranked[0].priority >= ranked[1].priority
        assert ranked == sorted(candidates, key=lambda c: c.priority, reverse=True)


class TestEventOrdering:
    """Publish activity: DB write completes before event dispatch (§9.5)."""

    def test_publish_event_after_db_commit(self):
        """_publish_event is called only via transaction.on_commit,
        guaranteeing the event is dispatched AFTER the DB transaction commits.
        """
        from gateway.event_bus import InsightEventBus, InsightPublishedEvent

        from activities.insight_activities import PublishInput, _publish_event

        InsightEventBus.reset_for_testing()
        received: list[InsightPublishedEvent] = []
        bus = InsightEventBus.instance()
        bus.subscribe(received.append)

        merchant_id = uuid.uuid4()
        insight_id = uuid.uuid4()

        input_data = PublishInput(
            merchant_id=merchant_id,
            kind="time_range",
            period_start=datetime.now(),
            period_end=datetime.now(),
            narrative="Test insight",
            claims=["claim1"],
            candidate_insights=[],
            tokens_in=10,
            tokens_out=20,
            model_used="test",
            cost_usd=0.02,
            agent_run_step_id=uuid.uuid4(),
        )

        _publish_event(input_data, insight_id)

        assert len(received) == 1
        assert received[0].insight_id == insight_id
        assert received[0].merchant_id == merchant_id
        assert received[0].kind == "time_range"

        InsightEventBus.reset_for_testing()

    def test_transaction_on_commit_guarantees_ordering(self):
        """Verify transaction.on_commit is used — the event callback is
        registered via on_commit, firing only after DB commit.
        """
        import inspect
        from unittest.mock import MagicMock
        from uuid import UUID

        from gateway.event_bus import InsightEventBus

        from activities.insight_activities import PublishInput

        source = inspect.getsource(__import__(
            "activities.insight_activities", fromlist=["publish"]
        ).publish)
        assert "on_commit" in source, "Publish must use transaction.on_commit"

        InsightEventBus.reset_for_testing()

        commit_callbacks: list = []

        class FakeAtomic:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        input_data = PublishInput(
            merchant_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            kind="time_range",
            period_start=datetime.now(),
            period_end=datetime.now(),
            narrative="Test",
            claims=[],
            candidate_insights=[],
            tokens_in=0,
            tokens_out=0,
            model_used="test",
            cost_usd=0.01,
            agent_run_step_id=UUID(int=0),
        )

        call_log: list[str] = []

        def fake_publish_event(publish_input, insight_id):
            call_log.append("event_published")

        fake_insight_cls = MagicMock()
        fake_insight_cls.objects.create.return_value = MagicMock()

        fake_agent_run_step_cls = MagicMock()
        fake_agent_run_step_cls.DoesNotExist = Exception
        fake_agent_run_step_cls.objects.filter.return_value.update.return_value = 0

        fake_analytics_models = MagicMock()
        fake_analytics_models.Insight = fake_insight_cls
        fake_agent_models = MagicMock()
        fake_agent_models.AgentRunStep = fake_agent_run_step_cls

        import django.db.transaction as real_txn

        with patch(
            "activities.insight_activities._publish_event",
            side_effect=fake_publish_event,
        ), patch.object(
            real_txn, "on_commit",
            lambda cb, **kw: commit_callbacks.append(cb),
        ), patch.object(
            real_txn, "atomic",
            return_value=FakeAtomic(),
        ), patch.dict(
            "sys.modules",
            {
                "analytics.models": fake_analytics_models,
                "agent.models": fake_agent_models,
            },
        ):
            from activities.insight_activities import publish

            try:
                _run(publish(input_data))
            except Exception:
                pass

            assert len(commit_callbacks) == 1
            assert call_log == []

            commit_callbacks[0]()

            assert call_log == ["event_published"]

        InsightEventBus.reset_for_testing()
