"""Pluggable telemetry sources for the SOC dashboard."""

from __future__ import annotations

from .base import MetricsProvider, Source, SourceStatus
from .metrics_source import PsutilMetricsProvider
from .netconn_source import NetConnSource
from .process_source import ProcessSource
from .simulator_source import SimulatedMetricsProvider, SimulatorEventSource
from .winevent_source import WinEventLogSource

__all__ = [
    "MetricsProvider", "Source", "SourceStatus",
    "build_sources", "build_metrics_provider",
]

_REAL_SOURCE_CLASSES = (NetConnSource, ProcessSource, WinEventLogSource)


def build_sources(mode: str) -> tuple[list[Source], list[SourceStatus]]:
    """Return (active_sources, all_statuses) for the given SOC_MODE.

    demo  -> simulator only
    live  -> real sources only (those whose preflight passes)
    blend -> simulator + real sources
    """
    sources: list[Source] = []
    statuses: list[SourceStatus] = []

    if mode in ("demo", "blend"):
        sources.append(SimulatorEventSource())

    if mode in ("live", "blend"):
        for cls in _REAL_SOURCE_CLASSES:
            src = cls()
            status = src.preflight()
            statuses.append(status)
            if status.available:
                sources.append(src)

    return sources, statuses


def build_metrics_provider(mode: str) -> MetricsProvider:
    """Simulated metrics in demo mode; real psutil metrics otherwise."""
    if mode == "demo":
        return SimulatedMetricsProvider()
    return PsutilMetricsProvider()
