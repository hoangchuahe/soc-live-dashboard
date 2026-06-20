from __future__ import annotations

from ..simulator import CampaignDirector, maybe_event, next_metrics
from .base import SourceStatus


class SimulatorEventSource:
    """Wraps the existing simulator, tagging every event as simulated.

    Each poll returns any due multi-stage campaign events plus one-off noise.
    """

    name = "simulator.attack"
    dataset = "simulator.attack"
    interval_seconds = 1.0

    def __init__(self) -> None:
        self._director = CampaignDirector()

    def preflight(self) -> SourceStatus:
        return SourceStatus(name=self.name, available=True, detail="ok")

    def poll(self) -> list[dict]:
        events = self._director.poll()
        noise = maybe_event()
        if noise is not None:
            events.append(noise)
        for event in events:
            event.setdefault("event", {})["dataset"] = self.dataset
            event["labels"] = {"provenance": "simulated"}
        return events


class SimulatedMetricsProvider:
    """Synthetic stats-bar metrics (demo mode)."""

    name = "host.metrics"

    def preflight(self) -> SourceStatus:
        return SourceStatus(name=self.name, available=True, detail="ok")

    def read(self) -> dict:
        return next_metrics()
