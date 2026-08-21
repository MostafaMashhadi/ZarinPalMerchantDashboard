from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol
from uuid import UUID

from shared.dtos import (
    AnalysisParams,
    AnalysisResult,
    DraftChunk,
    DraftRequest,
    DraftResponse,
    ProvenanceSpec,
)


class AnalysisStrategy(Protocol):
    def compute(self, merchant_id: UUID, params: AnalysisParams) -> AnalysisResult: ...

    def required_provenance(self) -> list[ProvenanceSpec]: ...


class LLMProviderAdapter(Protocol):
    """Normalizes AvalAI (or any future provider) into DraftRequest / DraftResponse.

    Used identically by the agentic Orchestrator and the Chat Turn Orchestrator.
    Concrete adapters (e.g. AvalAIAdapter) land in Sprint 3.
    """

    def complete(self, request: DraftRequest) -> DraftResponse: ...

    def stream(self, request: DraftRequest) -> Iterator[DraftChunk]: ...


class ChatResponseDeliveryStrategy(Protocol):
    """Streaming vs buffered delivery of a grounded chat answer. Sprint 3."""

    def deliver(self, draft: DraftResponse) -> Iterator[str] | str: ...
