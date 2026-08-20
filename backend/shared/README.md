# shared

Installable Python package imported by `api`, `mcp-server`, `temporal-worker`, and `notification-worker` without pulling in Django.

From each of those four services:

```bash
pip install -e ../shared
```

(Or `pip install -e ./shared` from `backend/`.)

Holds value objects (`FeeProxyValue`, `Money`), DTOs, `AnalysisStrategy`, and (from Sprint 3) `LLMProviderAdapter` and `ChatResponseDeliveryStrategy`.
