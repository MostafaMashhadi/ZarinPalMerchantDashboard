from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ProvenanceSpec:
    source_query_id: str
    clickhouse_sql: str
    query_params: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True)
class AnalysisParams:
    period_start: datetime
    period_end: datetime
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisResult:
    kind: str
    merchant_id: UUID
    period_start: datetime
    period_end: datetime
    headline: str
    body: dict[str, Any]
    series: tuple[Any, ...] = ()
    low_confidence_peer_set: bool = False
    provenance: tuple[ProvenanceSpec, ...] = ()
    ingest_batch_id: UUID | None = None


@dataclass(frozen=True)
class SourcedClaim:
    claim: str
    value: str | int | float
    source_insight_id: UUID | None = None


@dataclass(frozen=True)
class DraftRequest:
    scope: str  # "agent" | "chat"
    estimated_tokens: int
    system_prompt: str
    context: dict[str, Any]
    stream: bool = False


@dataclass(frozen=True)
class DraftChunk:
    text: str
    done: bool = False


@dataclass(frozen=True)
class DraftResponse:
    narrative: str
    claims: tuple[SourcedClaim, ...]
    tokens_in: int
    tokens_out: int
    model: str
    tier: str


ANALYSIS_KINDS: tuple[str, ...] = (
    "time_range",
    "event_impact",
    "cohort_retention",
    "peer_comparison",
    "anomaly_detection",
)
