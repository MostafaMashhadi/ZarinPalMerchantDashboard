"""ChatGroundingValidator — validates LLM-drafted content against structured data (§9.6.4).

On grounding failure, retries the Draft at the same checkpoint (max 2 retries).
On exhaustion, falls back to deterministic template composition.

Also validates:
- No adjusted_fee-derived number rendered with a currency unit (FeeProxyValue guardrail philosophy)
- If low_confidence_peer_set is true, requires disclaimer language or forces retry/fallback
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from shared.dtos import SourcedClaim


@dataclass(frozen=True, slots=True)
class GroundingResult:
    valid: bool
    ungrounded_values: list[str] = field(default_factory=list)
    reason: str = ""


class GroundingCheck(ABC):
    """Abstract grounding check (§9.6.4)."""

    @abstractmethod
    def check(
        self, narrative: str, claims: list[SourcedClaim], context: dict[str, Any]
    ) -> list[str]:
        """Return a list of violation descriptions; empty if valid."""
        ...


class NumericGroundingCheck(GroundingCheck):
    """Every numeric token in the narrative must be traceable to claims or context (§9.6.4)."""

    DATE_PATTERN = re.compile(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}(?:[-/]\d{1,2})?",
        re.IGNORECASE,
    )

    def check(
        self, narrative: str, claims: list[SourcedClaim], context: dict[str, Any]
    ) -> list[str]:
        allowed: set[str] = set()
        for c in claims:
            allowed.add(str(c.value))

        source_data = context.get("source_data", {})
        if isinstance(source_data, dict):
            for v in source_data.values():
                allowed.add(str(v))

        """Historical memory exception (§9.6.3, §9.6.4):
        Numbers recalled from MERCHANT_CHAT_MEMORY (past conversations beyond
        the 30-day raw window) are APPROXIMATE recollections, not fresh data
        assertions. They are NOT required to trace to a source_insight_id.
        This is a deliberate, narrow exception to the general grounding rule.
        We extract numeric tokens from key_facts so the narrative's numbers
        are matchable without falsely rejected.
        """
        historical = context.get("historical_memory", {})
        if isinstance(historical, dict) and historical.get("digest_available"):
            for mem in historical.get("memories", []):
                for fact in mem.get("key_facts", []):
                    for num in re.findall(r"[-+]?\d+(?:\.\d+)?", str(fact)):
                        allowed.add(num)

        narrative_clean = self.DATE_PATTERN.sub("", narrative)
        numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", narrative_clean)

        violations: list[str] = []
        for num_str in numbers:
            if num_str not in allowed:
                violations.append(f"Ungrounded value: '{num_str}'")
        return violations


class FeeProxyValueCheck(GroundingCheck):
    """No adjusted_fee-derived number rendered with a currency unit (§9.6.4).

    If a fee-related number appears alongside a currency unit (تومان, Toman,
    IRR, $), it must be traceable to the insight's fee data — adjusted fees
    are approximations and must not be presented as currency figures.
    """

    CURRENCY_UNITS = re.compile(
        r"(تومان|Toman|IRR|Rial|ریال|\$|USD|EUR)", re.IGNORECASE
    )
    FEE_KEYWORDS = re.compile(
        r"(fee|commission|rate|markup|spread|adjust)", re.IGNORECASE
    )

    def check(
        self, narrative: str, claims: list[SourcedClaim], context: dict[str, Any]
    ) -> list[str]:
        violations: list[str] = []
        fee_value_pattern = re.compile(r"[-+]?\d+(?:\.\d+)?")

        matches = list(fee_value_pattern.finditer(narrative))
        for match in matches:
            num_str = match.group()
            surrounding = narrative[max(0, match.start() - 30):match.end() + 30]

            has_currency = bool(self.CURRENCY_UNITS.search(surrounding))
            has_fee_context = bool(self.FEE_KEYWORDS.search(surrounding))

            if has_currency and has_fee_context:
                if num_str not in {str(c.value) for c in claims}:
                    violations.append(
                        f"Fee-proxy value '{num_str}' rendered as currency"
                    )
        return violations


class LowConfidenceDisclaimerCheck(GroundingCheck):
    """If low_confidence_peer_set is true, require disclaimer language (§9.6.4)."""

    DISCLAIMER_KEYWORDS = re.compile(
        r"(may vary|estimate|approximat|rough|based on limited data|"
        r"peer sample|caution|limited confidence)",
        re.IGNORECASE,
    )

    def check(
        self, narrative: str, claims: list[SourcedClaim], context: dict[str, Any]
    ) -> list[str]:
        if not context.get("low_confidence_peer_set", False):
            return []
        if not self.DISCLAIMER_KEYWORDS.search(narrative):
            return [
                "Missing disclaimer for low_confidence_peer_set result"
            ]
        return []


class ChatGroundingValidator:
    """Validates LLM-drafted content against structured data (§9.6.4).

    Implements the retry-and-fallback pattern:
    - On failure, retry Draft at the same checkpoint (max 2 retries)
    - On exhaustion, use DeterministicTemplateFallback
    """

    MAX_RETRIES = 2

    def __init__(self) -> None:
        self._checks: list[GroundingCheck] = [
            NumericGroundingCheck(),
            FeeProxyValueCheck(),
            LowConfidenceDisclaimerCheck(),
        ]

    def validate(
        self,
        narrative: str,
        claims: list[SourcedClaim],
        context: dict[str, Any] | None = None,
    ) -> GroundingResult:
        """Validate a drafted narrative (§9.6.4)."""
        context = context or {}
        violations: list[str] = []
        for check in self._checks:
            violations.extend(check.check(narrative, claims, context))

        if violations:
            return GroundingResult(
                valid=False, ungrounded_values=violations, reason="; ".join(violations)
            )
        return GroundingResult(valid=True)


@dataclass(frozen=True, slots=True)
class TemplateField:
    name: str
    source: str  # "claims", "analysis_result", "system"


class DeterministicTemplateFallback:
    """Deterministic template composition for chat (§9.6.4).

    When LLM drafting fails grounding repeatedly, fall back to composing
    the answer from structured data using predefined templates. No LLM call
    beyond the cheap IntentResolver classification.

    This is a P0 correctness requirement: the chat must always produce
    a traceable, grounded answer.
    """

    TEMPLATE_MAP: ClassVar[dict[str, str]] = {
        "time_range": (
            "In {period_start} to {period_end}: "
            "{headline}. "
            "Volume: {volume} {currency}. "
            "Success rate: {success_rate}%. "
            "Reference: insight {insight_id}."
        ),
        "event_impact": (
            "Event impact ({period_start} to {period_end}): "
            "{headline}. "
            "Affected transactions: {affected_count}. "
            "Revenue delta: {delta} {currency}. "
            "Reference: insight {insight_id}."
        ),
        "cohort_retention": (
            "Cohort retention ({period_start} to {period_end}): "
            "{headline}. "
            "Retention rate: {retention_rate}%. "
            "Reference: insight {insight_id}."
        ),
        "peer_comparison": (
            "Peer comparison ({period_start} to {period_end}): "
            "{headline}. "
            "Your {metric}: {your_value}. "
            "Peer average: {peer_value}. "
            "Percentile: {percentile}%. "
            "Reference: insight {insight_id}."
        ),
        "anomaly_detection": (
            "Anomaly detected ({period_start} to {period_end}): "
            "{headline}. "
            "Flagged clusters: {flagged_count}. "
            "Reference: insight {insight_id}."
        ),
        "general": (
            "Based on the analysis: {headline}. "
            "Reference: insight {insight_id}."
        ),
    }

    def render(
        self,
        kind: str,
        insight_result: dict[str, Any],
        *,
        merchant_id: str = "",
    ) -> tuple[str, list[SourcedClaim]]:
        """Render a deterministic answer from the structured AnalysisResult (§9.6.4).

        Returns (narrative, claims) tuple. Every number in the narrative
        is traceable to the insight's structured data.
        """
        template = self.TEMPLATE_MAP.get(kind, self.TEMPLATE_MAP["general"])

        body = insight_result.get("body", {})
        claims = self._extract_claims(insight_result, kind)

        context: dict[str, Any] = {
            "period_start": insight_result.get("period_start", ""),
            "period_end": insight_result.get("period_end", ""),
            "headline": insight_result.get("headline", "No headline available"),
            "insight_id": insight_result.get("insight_id", "unknown"),
            "currency": "Toman",
        }

        context.update(body)

        narrative = template.format(**context)

        return narrative, claims

    def _extract_claims(
        self, insight_result: dict[str, Any], kind: str
    ) -> list[SourcedClaim]:
        """Extract SourcedClaim objects from the structured result (§9.6.4)."""
        body = insight_result.get("body", {})
        insight_id = insight_result.get("insight_id")
        claims: list[SourcedClaim] = []

        if kind == "time_range":
            if "volume" in body:
                claims.append(SourcedClaim("volume", body["volume"], insight_id))
            if "success_rate" in body:
                claims.append(SourcedClaim("success_rate", body["success_rate"], insight_id))
        elif kind == "event_impact":
            if "affected_count" in body:
                claims.append(SourcedClaim("affected_count", body["affected_count"], insight_id))
            if "delta" in body:
                claims.append(SourcedClaim("delta", body["delta"], insight_id))
        elif kind == "cohort_retention":
            if "retention_rate" in body:
                claims.append(SourcedClaim("retention_rate", body["retention_rate"], insight_id))
        elif kind == "peer_comparison":
            if "your_value" in body:
                claims.append(SourcedClaim("your_value", body["your_value"], insight_id))
            if "peer_value" in body:
                claims.append(SourcedClaim("peer_value", body["peer_value"], insight_id))
            if "percentile" in body:
                claims.append(SourcedClaim("percentile", body["percentile"], insight_id))
        elif kind == "anomaly_detection":
            if "flagged_count" in body:
                claims.append(
                    SourcedClaim(
                        "flagged_count", body["flagged_count"], insight_id
                    )
                )

        return claims


__all__ = [
    "ChatGroundingValidator",
    "DeterministicTemplateFallback",
    "GroundingCheck",
    "GroundingResult",
]
