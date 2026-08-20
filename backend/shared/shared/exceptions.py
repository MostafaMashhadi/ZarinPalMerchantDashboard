class ProviderError(Exception):
    """Raised when an LLM provider call fails (retry / failover)."""


class AllProvidersExhausted(Exception):
    """Raised when every ModelTierHandler in the chain declined or failed."""
