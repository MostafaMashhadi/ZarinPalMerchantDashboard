"""AvalAIAdapter — translates DraftRequest/DraftResponse into AvalAI's wire format (§6.3, §9.3).

Implements LLMProviderAdapter. Both complete() (agentic path) and stream()
(chat path, §9.6.6) are implemented this task. A second provider = one new
Adapter class, no other changes.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from shared.dtos import DraftChunk, DraftRequest, DraftResponse, SourcedClaim
from shared.exceptions import ProviderError


@dataclass(frozen=True, slots=True)
class AvalAITierConfig:
    """Per-tier model configuration from environment (§6.3)."""

    tier: str
    model: str
    max_tokens: int
    temperature: float


_TIER_CONFIGS: dict[str, AvalAITierConfig] = {
    "cheap": AvalAITierConfig(
        tier="cheap",
        model=os.environ.get("AVALAI_CHEAP_MODEL", "cheap-tier"),
        max_tokens=1000,
        temperature=0.3,
    ),
    "mid": AvalAITierConfig(
        tier="mid",
        model=os.environ.get("AVALAI_MID_MODEL", "mid-tier"),
        max_tokens=2000,
        temperature=0.4,
    ),
    "premium": AvalAITierConfig(
        tier="premium",
        model=os.environ.get("AVALAI_PREMIUM_MODEL", "premium-tier"),
        max_tokens=4000,
        temperature=0.5,
    ),
}


def get_tier_config(tier: str) -> AvalAITierConfig:
    if tier not in _TIER_CONFIGS:
        raise ValueError(f"Unknown tier: {tier}")
    return _TIER_CONFIGS[tier]


# Approximate tokens-per-USD rates per tier for cost estimation (§9.3).
# Used by CostLedger to convert token estimates to USD.
TOKENS_PER_USD: dict[str, int] = {
    "cheap": 20000,
    "mid": 8000,
    "premium": 2000,
}


def estimate_cost_usd(tier: str, tokens: int) -> float:
    """Estimate cost in USD for a given token count and tier."""
    rate = TOKENS_PER_USD.get(tier, TOKENS_PER_USD["cheap"])
    if rate == 0:
        return 0.0
    return tokens / rate


class AvalAIAdapter:
    """Adapter for AvalAI's OpenAI-compatible API (§6.3, §9.3).

    Translates provider-agnostic DraftRequest into AvalAI's wire format
    and back. The tier is embedded in DraftRequest.context['tier'].
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._api_key = api_key or os.environ.get("AVALAI_API_KEY", "")
        self._base_url = base_url or os.environ.get("AVALAI_BASE_URL", "https://api.avalai.ir/v1")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=30.0,
            )
        return self._client

    def _resolve_tier(self, request: DraftRequest) -> AvalAITierConfig:
        tier = request.context.get("tier", "cheap")
        return get_tier_config(tier)

    def _build_request_body(
        self, request: DraftRequest, config: AvalAITierConfig
    ) -> dict[str, Any]:
        system_prompt = request.system_prompt
        user_content = json.dumps(
            request.context.get("structured_context", {}),
            ensure_ascii=False,
        )

        return {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "response_format": {"type": "json_object"},
        }

    def _parse_response(self, raw: dict[str, Any]) -> DraftResponse:
        message = raw["choices"][0]["message"]
        content = message.get("content", "{}")

        try:
            structured = json.loads(content)
        except json.JSONDecodeError:
            structured = {"narrative": content, "claims": []}

        claims = []
        for c in structured.get("claims", []):
            claims.append(
                SourcedClaim(
                    claim=c.get("claim", ""),
                    value=c.get("value", ""),
                    source_insight_id=c.get("source_insight_id"),
                )
            )

        usage = raw.get("usage", {})
        return DraftResponse(
            narrative=structured.get("narrative", ""),
            claims=tuple(claims),
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            model=raw.get("model", "unknown"),
            tier=structured.get("tier", "unknown"),
        )

    async def complete(self, request: DraftRequest) -> DraftResponse:
        """Synchronous completion call (used by agentic path, §19.16/§19.17).

        Raises ProviderError on transient failures; never raises on success.
        """
        config = self._resolve_tier(request)
        body = self._build_request_body(request, config)

        try:
            resp = await self.client.post("/chat/completions", json=body)
            resp.raise_for_status()
            return self._parse_response(resp.json())
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise ProviderError(f"AvalAI API error: {exc}") from exc

    def stream(self, request: DraftRequest) -> Iterator[DraftChunk]:
        """Streaming completion (used by chat path, §9.6.6).

        Yields DraftChunk objects as they arrive from the provider.
        Raises ProviderError on transient failures.
        """
        config = self._resolve_tier(request)
        body = self._build_request_body(request, config)
        body["stream"] = True

        try:
            resp = self.client.post("/chat/completions", json=body, stream=True)
            resp = resp.__enter__()

            for line in resp.iter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data == "[DONE]":
                        yield DraftChunk(text="", done=True)
                        break
                    try:
                        chunk = json.loads(data)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:
                            yield DraftChunk(text=content, done=False)
                    except (json.JSONDecodeError, KeyError):
                        continue
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise ProviderError(f"AvalAI stream error: {exc}") from exc

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


__all__ = [
    "AvalAIAdapter",
    "AvalAITierConfig",
    "TOKENS_PER_USD",
    "estimate_cost_usd",
    "get_tier_config",
]
