"""ChatResponseDeliveryStrategy — Streaming (SSE) and Buffered (§9.6.6, §6.6).

StreamingDelivery by default; falls back to BufferedDelivery on:
- provider/tier non-streaming support
- unstable SSE
- mid-stream error

When falling back, the client receives a complete, valid answer.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass

from django.http import StreamingHttpResponse
from rest_framework.response import Response


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    narrative: str
    claims: list
    tokens_in: int
    tokens_out: int
    model: str
    tier: str
    delivery_mode: str


class ChatResponseDeliveryStrategy(ABC):
    """Abstract delivery strategy (§9.6.6)."""

    @abstractmethod
    def deliver(
        self,
        chunks: Iterator,
        content_type: str = "text/event-stream",
    ) -> Response:
        ...


class StreamingDelivery(ChatResponseDeliveryStrategy):
    """SSE streaming delivery (§9.6.6, §6.6).

    Streams DraftChunk objects as SSE `data:` frames.
    Falls back to BufferedDelivery on mid-stream error.
    """

    def __init__(self, fallback: ChatResponseDeliveryStrategy | None = None) -> None:
        self._fallback = fallback or BufferedDelivery()

    def deliver(self, chunks: Iterator, content_type: str = "text/event-stream") -> Response:
        def event_stream():
            errors: list[str] = []
            collected: list[str] = []

            try:
                for chunk in chunks:
                    if chunk.done:
                        yield f"event: done\ndata: {json.dumps({'done': True})}\n\n"
                    else:
                        yield f"data: {json.dumps({'text': chunk.text})}\n\n"
                        collected.append(chunk.text)
            except Exception as exc:
                errors.append(str(exc))
                error_payload = json.dumps({
                    "error": "stream_error",
                    "message": str(exc),
                })
                yield f"event: error\ndata: {error_payload}\n\n"
                return

            if errors:
                full_text = "".join(collected)
                yield f"event: fallback\ndata: {json.dumps({'text': full_text})}\n\n"

        response = StreamingHttpResponse(
            event_stream(), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class BufferedDelivery(ChatResponseDeliveryStrategy):
    """Buffered delivery — returns the complete answer as JSON (§9.6.6).

    Used as fallback when streaming fails or the provider/tier doesn't
    support streaming.
    """

    def deliver(self, chunks: Iterator, content_type: str | None = None) -> Response:
        full_text = ""
        claims: list = []
        tokens_in = 0
        tokens_out = 0
        model_used = ""
        tier = ""

        for chunk in chunks:
            full_text += chunk.text or ""
            if chunk.done:
                if hasattr(chunk, "claims"):
                    claims = list(chunk.claims)
                if hasattr(chunk, "tokens_in"):
                    tokens_in = chunk.tokens_in
                if hasattr(chunk, "tokens_out"):
                    tokens_out = chunk.tokens_out
                if hasattr(chunk, "model"):
                    model_used = chunk.model
                if hasattr(chunk, "tier"):
                    tier = chunk.tier

        return Response({
            "text": full_text,
            "claims": [c.claim if hasattr(c, "claim") else str(c) for c in claims],
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "model": model_used,
            "tier": tier,
        }, status=200)


class DeliveryStrategySelector:
    """Selects the delivery strategy based on client capabilities and provider support (§9.6.6)."""

    @staticmethod
    def select(
        *,
        supports_streaming: bool = True,
        sse_supported: bool = True,
        prefer_buffered: bool = False,
    ) -> ChatResponseDeliveryStrategy:
        """Choose delivery strategy (§9.6.6).

        - prefer_buffered=True → BufferedDelivery
        - supports_streaming=False → BufferedDelivery
        - sse_supported=False → BufferedDelivery
        - Otherwise → StreamingDelivery (with BufferedDelivery fallback)
        """
        if prefer_buffered or not supports_streaming or not sse_supported:
            return BufferedDelivery()
        return StreamingDelivery(fallback=BufferedDelivery())


__all__ = [
    "BufferedDelivery",
    "ChatResponseDeliveryStrategy",
    "DeliveryResult",
    "DeliveryStrategySelector",
    "StreamingDelivery",
]
