"""AnalysisStrategyFactory — single point of truth mapping analysis kinds to strategies (§6.2).

Controllers/Facades — including ChatFacade's tool-routing layer — call
factory.create(kind) and never import a concrete Strategy class directly.
"""

from __future__ import annotations

from typing import ClassVar

from analytics.strategies.anomaly_detection import AnomalyDetectionAnalysisStrategy
from analytics.strategies.cohort_retention import CohortRetentionAnalysisStrategy
from analytics.strategies.event_impact import EventImpactAnalysisStrategy
from analytics.strategies.peer_comparison import PeerComparisonAnalysisStrategy
from analytics.strategies.time_range import TimeRangeAnalysisStrategy
from shared.dtos import ANALYSIS_KINDS
from shared.protocols import AnalysisStrategy


class AnalysisStrategyFactory:
    """Maps an analysis 'kind' string to a Strategy instance.

    The spec (§6.2) shows the registry as string class names, but the
    actual implementation uses real class references so the factory
    can instantiate directly without getattr lookups.
    """

    _registry: ClassVar[dict[str, type[AnalysisStrategy]]] = {
        "time_range": TimeRangeAnalysisStrategy,
        "event_impact": EventImpactAnalysisStrategy,
        "cohort_retention": CohortRetentionAnalysisStrategy,
        "peer_comparison": PeerComparisonAnalysisStrategy,
        "anomaly_detection": AnomalyDetectionAnalysisStrategy,
    }

    def create(self, kind: str) -> AnalysisStrategy:
        if kind not in ANALYSIS_KINDS:
            raise ValueError(f"Unknown analysis kind: {kind}")
        strategy_cls = self._registry.get(kind)
        if strategy_cls is None:
            raise NotImplementedError(
                f"Analysis kind '{kind}' is recognized but not yet implemented. "
                f"Registered kinds: {list(self._registry.keys())}"
            )
        return strategy_cls()


__all__ = ["AnalysisStrategyFactory"]
