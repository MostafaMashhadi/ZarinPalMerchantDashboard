"""IntentResolver — classifies a chat message into a specific (kind, params) or
general/out-of-scope (§9.6.3, step 2).

Uses Strategy pattern: each resolver is a Strategy object that attempts to
classify the message. Resolvers are tried in order of specificity; the first
one that yields a match wins. This avoids if/elif ladders.

Fast path: regex-based keyword matching for known query patterns.
LLM path: delegates to a cheap-tier LLM call for ambiguous questions.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from gateway.adapters.avalai_adapter import AvalAIAdapter
from shared.dtos import DraftRequest


@dataclass(frozen=True, slots=True)
class IntentClass:
    """The result of resolving a chat message's intent."""

    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


class IntentResolverStrategy(ABC):
    """Base strategy for intent classification (§9.6.3, §5.2)."""

    @abstractmethod
    def resolve(self, message: str) -> IntentClass | None:
        """Return an IntentClass if this strategy recognizes the intent,
        or None to defer to the next strategy in the chain."""
        ...


class KeywordTimeRangeResolver(IntentResolverStrategy):
    """Fast-path: keywords indicating a time-range analysis request."""

    PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (
            r"\b(revenue|volume|transaction|payment|success rate|refund)\b"
            r".*\b(last|this|past|since|from|between|during)\s+\w+",
            "time_range",
        ),
        (
            r"\b(how much|what was|total|sum)\b"
            r".*\b(last|this|past|since|from)\s+\w+",
            "time_range",
        ),
        (
            r"\b(period|month|week|day|quarter|year)\s+\b(revenue|volume|total)\b",
            "time_range",
        ),
    ]

    def resolve(self, message: str) -> IntentClass | None:
        for pattern, kind in self.PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return IntentClass(kind=kind, params={}, confidence=0.7)
        return None


class KeywordEventImpactResolver(IntentResolverStrategy):
    """Fast-path: keywords indicating an event-impact analysis request."""

    PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (
            r"\b(chargeback|dispute|scam|fraud|issue|problem|bug|outage)\b",
            "event_impact",
        ),
        (
            r"\b(effect|impact|affected|affect)\b"
            r".*\b(revenue|volume|transactions)\b",
            "event_impact",
        ),
        (
            r"\b(during|after|when)\b.*\b(chargeback|dispute|issue|fraud)\b",
            "event_impact",
        ),
    ]

    def resolve(self, message: str) -> IntentClass | None:
        for pattern, kind in self.PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return IntentClass(kind=kind, params={}, confidence=0.7)
        return None


class KeywordPeerComparisonResolver(IntentResolverStrategy):
    """Fast-path: keywords indicating a peer-comparison analysis request."""

    PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (
            r"\b(compare|vs |versus|vs\.|percentile|peer|benchmark)\b",
            "peer_comparison",
        ),
        (
            r"\b(how do i|am i|better|worse|ranking)\b"
            r".*\b(than|compared to|vs)\b",
            "peer_comparison",
        ),
    ]

    def resolve(self, message: str) -> IntentClass | None:
        for pattern, kind in self.PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return IntentClass(kind=kind, params={}, confidence=0.7)
        return None


class KeywordCohortRetentionResolver(IntentResolverStrategy):
    """Fast-path: keywords indicating a cohort-retention analysis request."""

    PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (
            r"\b(retention|cohort|repeat|returning|churn)\b",
            "cohort_retention",
        ),
        (
            r"\b(keep|retain|lost|churned)\b"
            r".*\b(customers|merchants|users)\b",
            "cohort_retention",
        ),
    ]

    def resolve(self, message: str) -> IntentClass | None:
        for pattern, kind in self.PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return IntentClass(kind=kind, params={}, confidence=0.7)
        return None


class KeywordAnomalyResolver(IntentResolverStrategy):
    """Fast-path: keywords indicating an anomaly-detection request."""

    PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (
            r"\b(anomal|spike|drop|unusual|unexpected|odd|strange)\b",
            "anomaly_detection",
        ),
        (
            r"\b(what's|what is)\b.*\b(wrong|suspicious|fraud)\b",
            "anomaly_detection",
        ),
    ]

    def resolve(self, message: str) -> IntentClass | None:
        for pattern, kind in self.PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return IntentClass(kind=kind, params={}, confidence=0.7)
        return None


class GeneralGuidanceResolver(IntentResolverStrategy):
    """Fallback: classify as general-guidance (still answerable by LLM)."""

    GENERAL_KEYWORDS: ClassVar[list[str]] = [
        "how", "what", "why", "can you", "tell me", "explain",
        "help", "guide", "best practice", "recommend",
        "should", "could", "would", "do you",
    ]

    def resolve(self, message: str) -> IntentClass | None:
        lower = message.lower()
        if any(kw in lower for kw in self.GENERAL_KEYWORDS):
            return IntentClass(kind="general", params={}, confidence=0.5)
        return None


class OutOfScopeResolver(IntentResolverStrategy):
    """Last-resort: anything that doesn't match is out of scope."""

    def resolve(self, message: str) -> IntentClass | None:
        return IntentClass(kind="out_of_scope", params={}, confidence=0.3)


class LLMIntentResolver(IntentResolverStrategy):
    """LLM-based resolver: delegates classification to a cheap-tier LLM call."""

    SYSTEM_PROMPT = (
        "Classify the following user message into one of: "
        "time_range, event_impact, cohort_retention, "
        "peer_comparison, anomaly_detection, general, "
        "out_of_scope. Return ONLY the kind string."
    )

    def __init__(self, adapter: AvalAIAdapter | None = None) -> None:
        self._adapter = adapter or AvalAIAdapter()

    def resolve(self, message: str) -> IntentClass | None:
        try:
            import asyncio

            request = DraftRequest(
                scope="chat",
                estimated_tokens=100,
                system_prompt=self.SYSTEM_PROMPT,
                context={"tier": "cheap", "merchant_id": "", "message": message},
                stream=False,
            )
            response = asyncio.run(self._adapter.complete(request))
            kind = response.narrative.strip().lower()
            if kind in (
                "time_range", "event_impact", "cohort_retention",
                "peer_comparison", "anomaly_detection",
                "general", "out_of_scope",
            ):
                return IntentClass(kind=kind, params={}, confidence=0.8)
        except Exception:
            pass
        return None


class IntentResolver:
    """Strategy-pattern intent classifier (§9.6.3, step 2).

    Tries keyword resolvers first (deterministic, fast, token-free),
    then LLM resolver (cheap tier), then general guidance, then out-of-scope.
    """

    _ANALYSIS_KINDS: ClassVar[set[str]] = {
        "time_range", "event_impact", "cohort_retention",
        "peer_comparison", "anomaly_detection",
    }

    def __init__(
        self,
        *,
        llm_adapter: AvalAIAdapter | None = None,
        use_llm: bool = True,
    ) -> None:
        self._strategies: list[IntentResolverStrategy] = [
            KeywordTimeRangeResolver(),
            KeywordEventImpactResolver(),
            KeywordPeerComparisonResolver(),
            KeywordCohortRetentionResolver(),
            KeywordAnomalyResolver(),
        ]
        self._llm_resolver = LLMIntentResolver(llm_adapter) if use_llm else None
        self._fallback = GeneralGuidanceResolver()
        self._last_resort = OutOfScopeResolver()

    def resolve(self, message: str) -> IntentClass:
        """Resolve the intent of a user message (§9.6.3, step 2).

        Order: keyword resolvers (fast, deterministic) then LLM (cheap tier),
        then general guidance, then out-of-scope.
        """
        for strategy in self._strategies:
            result = strategy.resolve(message)
            if result is not None:
                return result

        if self._llm_resolver is not None:
            result = self._llm_resolver.resolve(message)
            if result is not None and result.kind in self._ANALYSIS_KINDS:
                return result

        result = self._fallback.resolve(message)
        if result is not None:
            return result

        return self._last_resort.resolve(message)


__all__ = [
    "IntentClass",
    "IntentResolver",
    "IntentResolverStrategy",
]
