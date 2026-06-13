from __future__ import annotations

from ..simulator import maybe_event, next_metrics
from .base import SourceStatus


class SimulatorEventSource:
    """Wraps the existing simulator, tagging every event as simulated."""

    name = "simulator.attack"
    dataset = "simulator.attack"
    interval_seconds = 1.0

    def preflight(self) -> SourceStatus:
        return SourceStatus(name=self.name, available=True, detail="ok")

    def poll(self) -> list[dict]:
        event = maybe_event()
        if event is None:
            return []
        event.setdefault("event", {})["dataset"] = self.dataset
        event["labels"] = {"provenance": "simulated"}
        return [event]


class SimulatedMetricsProvider:
    """Synthetic stats-bar metrics (demo mode)."""

    name = "host.metrics"

    def preflight(self) -> SourceStatus:
        return SourceStatus(name=self.name, available=True, detail="ok")

    def read(self) -> dict:
        return next_metrics()
