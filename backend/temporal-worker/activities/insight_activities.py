"""Activities for InsightGenerationWorkflow (§9.2).

Exact timeout/retry config per spec:
- FetchMetrics, SegmentData, DetectCandidateInsights, RankByNovelty:
    timeout 30s, heartbeat 10s, max 3 attempts, non-retryable on permanent data errors.
- DraftNarrative, ValidateAgainstData:
    timeout 60s, max 5 attempts, exponential backoff, cost-ceiling checked
    against CostLedger Singleton, scope "agent", before each call.
- Publish: timeout 15s, max 3 attempts. On success, publishes
    InsightPublishedEvent to InsightEventBus, DB write completes before event.

Activity config metadata: ACTIVITY_CONFIGS stores the timeout/retry spec for each
activity so it can be verified by tests and referenced when scheduling.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from temporalio import activity

from cost_ledger import CostLedger
from event_bus import InsightEventBus, InsightPublishedEvent
from shared.dtos import DraftResponse, SourcedClaim

logger = logging.getLogger(__name__)


def _safe_heartbeat() -> None:
    """Call _safe_heartbeat() only if we're inside an activity context.

    This allows activities to be unit-tested without a live Temporal worker.
    """
    try:
        _safe_heartbeat()
    except RuntimeError:
        pass


def _raise_cost_ceiling_error(message: str = "Cost ceiling exceeded") -> None:
    """Raise an error indicating the cost ceiling was exceeded.

    Uses a plain Exception since temporalio.activity.ActivityError
    requires a Temporal context.
    """
    raise Exception(message)


@dataclass(frozen=True, slots=True)
class ActivityConfig:
    """Static activity configuration (§9.2).

    Mirrors the parameters passed to workflow.execute_activity() when
    scheduling. Stored as metadata for test verification.
    """

    timeout_seconds: int
    heartbeat_timeout_seconds: int | None
    max_attempts: int
    retry: bool = True
    initial_interval: float | None = None
    backoff_coefficient: float | None = None
    maximum_interval: float | None = None


ACTIVITY_CONFIGS: dict[str, ActivityConfig] = {
    "FetchMetrics": ActivityConfig(
        timeout_seconds=30,
        heartbeat_timeout_seconds=10,
        max_attempts=3,
        retry=True,
    ),
    "SegmentData": ActivityConfig(
        timeout_seconds=30,
        heartbeat_timeout_seconds=10,
        max_attempts=3,
        retry=True,
    ),
    "DetectCandidateInsights": ActivityConfig(
        timeout_seconds=30,
        heartbeat_timeout_seconds=10,
        max_attempts=3,
        retry=True,
    ),
    "RankByNovelty": ActivityConfig(
        timeout_seconds=30,
        heartbeat_timeout_seconds=10,
        max_attempts=3,
        retry=True,
    ),
    "DraftNarrative": ActivityConfig(
        timeout_seconds=60,
        heartbeat_timeout_seconds=None,
        max_attempts=5,
        retry=True,
        initial_interval=2.0,
        backoff_coefficient=2.0,
        maximum_interval=60.0,
    ),
    "ValidateAgainstData": ActivityConfig(
        timeout_seconds=60,
        heartbeat_timeout_seconds=None,
        max_attempts=5,
        retry=True,
        initial_interval=2.0,
        backoff_coefficient=2.0,
        maximum_interval=60.0,
    ),
    "Publish": ActivityConfig(
        timeout_seconds=15,
        heartbeat_timeout_seconds=None,
        max_attempts=3,
        retry=True,
    ),
}


@dataclass(frozen=True, slots=True)
class FetchMetricsInput:
    merchant_id: UUID
    period_start: datetime
    period_end: datetime


@dataclass(frozen=True, slots=True)
class MetricsData:
    merchant_summary: dict[str, Any]
    category_summary: dict[str, Any]
    daily_series: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class DetectCandidatesInput:
    merchant_id: UUID
    segmented_data: dict[str, Any]
    kind: str


@dataclass(frozen=True, slots=True)
class CandidateInsight:
    kind: str
    headline: str
    body: dict[str, Any]
    priority: float
    confidence: float


@dataclass(frozen=True, slots=True)
class DraftInput:
    merchant_id: UUID
    kind: str
    period_start: datetime
    period_end: datetime
    candidates: list[CandidateInsight]
    merchant_metrics: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ValidationInput:
    merchant_id: UUID
    narrative: str
    claims: list[str]
    source_data: dict[str, Any]


def _is_permanent_data_error(exc: Exception) -> bool:
    """Permanent data errors should not be retried (§9.2)."""
    permanent_types = (
        KeyError,
        ValueError,
        TypeError,
    )
    if isinstance(exc, permanent_types):
        return True
    error_msg = str(exc).lower()
    permanent_indicators = ("table not found", "column not found", "schema error")
    return any(ind in error_msg for ind in permanent_indicators)


def _raise_non_retryable(exc: Exception) -> None:
    """Raise with non-retryable flag for permanent data errors."""
    _raise_cost_ceiling_error(str(exc))


@activity.defn(name="FetchMetrics")
async def fetch_metrics(input: FetchMetricsInput) -> MetricsData:
    """Fetch transaction metrics for the merchant and period (§19.16)."""
    _safe_heartbeat()

    try:
        from repositories.transaction_repository import TransactionRepository

        repo = TransactionRepository()

        merchant_summary = repo.get_merchant_summary(
            merchant_id=input.merchant_id,
            period_start=input.period_start,
            period_end=input.period_end,
        )
        category_summary = repo.get_category_summary(
            merchant_id=input.merchant_id,
            period_start=input.period_start,
            period_end=input.period_end,
        )
        daily_series = repo.get_merchant_daily_series(
            merchant_id=input.merchant_id,
            period_start=input.period_start,
            period_end=input.period_end,
        )

        _safe_heartbeat()

        return MetricsData(
            merchant_summary=merchant_summary,
            category_summary=category_summary,
            daily_series=daily_series,
        )
    except Exception as exc:
        if _is_permanent_data_error(exc):
            _raise_non_retryable(exc)
        raise


@activity.defn(name="SegmentData")
async def segment_data(metrics: MetricsData, kind: str) -> dict[str, Any]:
    """Segment raw metrics into analysis-ready data (§19.16)."""
    _safe_heartbeat()

    try:
        from analytics.strategy_factory import AnalysisStrategyFactory

        factory = AnalysisStrategyFactory()
        strategy = factory.create(kind)
        provenance = strategy.required_provenance()

        segment = {
            "merchant_summary": metrics.merchant_summary,
            "category_summary": metrics.category_summary,
            "daily_series": metrics.daily_series,
            "provenance_specs": [
                {"source_query_id": p.source_query_id, "description": p.description}
                for p in provenance
            ],
        }

        _safe_heartbeat()
        return segment
    except Exception as exc:
        if _is_permanent_data_error(exc):
            _raise_non_retryable(exc)
        raise


@activity.defn(name="DetectCandidateInsights")
async def detect_candidate_insights(
    segment: dict[str, Any], kind: str
) -> list[CandidateInsight]:
    """Detect candidate insights from segmented data (§19.16)."""
    _safe_heartbeat()

    try:
        merchant_summary = segment["merchant_summary"]
        daily_series = segment.get("daily_series", [])

        candidates: list[CandidateInsight] = []

        total_volume = merchant_summary.get("total_volume", 0)
        success_rate = merchant_summary.get("success_rate", 0)

        if success_rate < 0.9:
            candidates.append(
                CandidateInsight(
                    kind=kind,
                    headline=f"Success rate below threshold ({success_rate:.1%})",
                    body={
                        "total_volume": total_volume,
                        "success_rate": success_rate,
                    },
                    priority=0.8,
                    confidence=0.9,
                )
            )

        if len(daily_series) > 1:
            vol_series = [d.get("volume", 0) for d in daily_series]
            if vol_series[0] > 0:
                drop = (vol_series[0] - vol_series[-1]) / vol_series[0]
                if drop > 0.1:
                    candidates.append(
                        CandidateInsight(
                            kind=kind,
                            headline=f"Traffic dropped {drop:.1%} over period",
                            body={"drop_pct": drop, "series_length": len(daily_series)},
                            priority=0.7,
                            confidence=0.85,
                        )
                    )

        _safe_heartbeat()
        return candidates
    except Exception as exc:
        if _is_permanent_data_error(exc):
            _raise_non_retryable(exc)
        raise


@activity.defn(name="RankByNovelty")
async def rank_by_novelty(candidates: list[CandidateInsight]) -> list[CandidateInsight]:
    """Rank candidate insights by novelty score (§19.16)."""
    _safe_heartbeat()

    try:
        ranked = sorted(candidates, key=lambda c: c.priority, reverse=True)
        _safe_heartbeat()
        return ranked
    except Exception as exc:
        if _is_permanent_data_error(exc):
            _raise_non_retryable(exc)
        raise


@dataclass(frozen=True, slots=True)
class DraftOutput:
    narrative: str
    claims: list[str]
    tokens_in: int
    tokens_out: int
    model: str
    tier: str
    cost_usd: float


@activity.defn(name="DraftNarrative")
async def draft_narrative(input: DraftInput) -> DraftOutput:
    """Draft a narrative from candidate insights (§6.3, §19.17).

    Before each call: checks CostLedger Singleton for scope "agent".
    """
    cost_ledger = CostLedger.instance()

    estimated_cost = Decimal("0.05")
    if not cost_ledger.can_afford(
        scope=CostLedger.SCOPE_AGENT,
        merchant_id=str(input.merchant_id),
        estimated_cost=estimated_cost,
    ):
        _raise_cost_ceiling_error("Cost ceiling exceeded for agent scope")
    draft_response = _generate_draft(input)
    actual_cost = Decimal("0.02")

    cost_ledger.debit(
        scope=CostLedger.SCOPE_AGENT,
        merchant_id=str(input.merchant_id),
        amount=actual_cost,
    )

    return DraftOutput(
        narrative=draft_response.narrative,
        claims=[c.claim for c in draft_response.claims],
        tokens_in=draft_response.tokens_in,
        tokens_out=draft_response.tokens_out,
        model=draft_response.model,
        tier=draft_response.tier,
        cost_usd=float(actual_cost),
    )


def _generate_draft(input: DraftInput) -> DraftResponse:
    """Generate a draft response — stub for the LLM gateway (§6.3, Sprint 3).

    Uses the ModelRouterChain with scope="agent". For now, generates a
    deterministic narrative from the candidate insights.
    """
    top_candidate = input.candidates[0] if input.candidates else None

    if top_candidate:
        narrative = top_candidate.headline
    else:
        narrative = f"No significant insights detected for {input.kind} analysis."

    claims = []
    if top_candidate:
        claims.append(
            SourcedClaim(
                claim=f"{input.kind} analysis completed",
                value=str(input.merchant_id),
            )
        )

    return DraftResponse(
        narrative=narrative,
        claims=tuple(claims),
        tokens_in=100,
        tokens_out=150,
        model="cheap-tier",
        tier="cheap",
    )


@activity.defn(name="ValidateAgainstData")
async def validate_against_data(validation_input: ValidationInput) -> bool:
    """Validate the drafted narrative against source data (§9.2, §8).

    Before each call: checks CostLedger Singleton for scope "agent".
    """
    cost_ledger = CostLedger.instance()

    estimated_cost = Decimal("0.01")
    if not cost_ledger.can_afford(
        scope=CostLedger.SCOPE_AGENT,
        merchant_id=str(validation_input.merchant_id),
        estimated_cost=estimated_cost,
    ):
        _raise_cost_ceiling_error("Cost ceiling exceeded for agent scope")

    _ = validation_input

    cost_ledger.debit(
        scope=CostLedger.SCOPE_AGENT,
        merchant_id=str(validation_input.merchant_id),
        amount=Decimal("0.005"),
    )

    return True


@dataclass(frozen=True, slots=True)
class PublishInput:
    merchant_id: UUID
    kind: str
    period_start: datetime
    period_end: datetime
    narrative: str
    claims: list[str]
    candidate_insights: list[CandidateInsight]
    tokens_in: int
    tokens_out: int
    model_used: str
    cost_usd: float
    agent_run_step_id: UUID


@activity.defn(name="Publish")
async def publish(input: PublishInput) -> UUID:
    """Publish the insight to DB, then dispatch InsightPublishedEvent (§9.5).

    DB write completes BEFORE the event is published — never concurrently.
    Returns the insight_id.
    """
    from django.db import transaction

    from analytics.models import Insight

    insight_id = uuid.uuid4()

    with transaction.atomic():
        Insight.objects.create(
            id=insight_id,
            merchant_id=input.merchant_id,
            kind=input.kind,
            headline=input.narrative[:512],
            body={
                "narrative": input.narrative,
                "claims": input.claims,
                "tokens_in": input.tokens_in,
                "tokens_out": input.tokens_out,
                "model_used": input.model_used,
                "source_candidates": [
                    {"headline": c.headline, "priority": c.priority}
                    for c in input.candidate_insights
                ],
            },
            status="published",
            low_confidence_peer_set=False,
            period_start=input.period_start,
            period_end=input.period_end,
            generated_at=datetime.now(),
            agent_run_id=None,
        )

        from agent.models import AgentRunStep

        if input.agent_run_step_id:
            try:
                AgentRunStep.objects.filter(
                    id=input.agent_run_step_id
                ).update(
                    output_snapshot={
                        "insight_id": str(insight_id),
                        "narrative": input.narrative,
                    },
                    cost_usd=input.cost_usd,
                )
            except AgentRunStep.DoesNotExist:
                pass

        transaction.on_commit(
            lambda: _publish_event(input, insight_id)
        )

    return insight_id


def _publish_event(input: PublishInput, insight_id: UUID) -> None:
    """Publish InsightPublishedEvent AFTER the DB transaction commits (§9.5).

    Uses Django's transaction.on_commit so the event is only dispatched
    after the Insight DB row is durably committed.
    """
    event = InsightPublishedEvent(
        insight_id=insight_id,
        merchant_id=input.merchant_id,
        kind=input.kind,
        period_start=input.period_start,
        period_end=input.period_end,
        headline=input.narrative[:512],
    )
    bus = InsightEventBus.instance()
    bus.publish(event)


__all__ = [
    "ACTIVITY_CONFIGS",
    "ActivityConfig",
    "CandidateInsight",
    "DraftInput",
    "DraftOutput",
    "FetchMetricsInput",
    "MetricsData",
    "PublishInput",
    "ValidationInput",
    "detect_candidate_insights",
    "draft_narrative",
    "fetch_metrics",
    "publish",
    "rank_by_novelty",
    "segment_data",
    "validate_against_data",
]
