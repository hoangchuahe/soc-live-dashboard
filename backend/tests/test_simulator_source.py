"""SimulatorEventSource + SimulatedMetricsProvider."""

from __future__ import annotations

from app.sources.base import MetricsProvider, Source
from app.sources.simulator_source import SimulatedMetricsProvider, SimulatorEventSource


def test_event_source_is_a_source():
    assert isinstance(SimulatorEventSource(), Source)


def test_event_source_tags_simulated(monkeypatch):
    fake_event = {"@timestamp": "t", "event": {"id": "e1", "category": "network",
                  "severity": "low"}, "message": "m"}
    monkeypatch.setattr("app.sources.simulator_source.maybe_event", lambda: fake_event)

    events = SimulatorEventSource().poll()

    assert len(events) == 1
    assert events[0]["labels"] == {"provenance": "simulated"}
    assert events[0]["event"]["dataset"] == "simulator.attack"


def test_event_source_empty_when_no_event(monkeypatch):
    monkeypatch.setattr("app.sources.simulator_source.maybe_event", lambda: None)
    assert SimulatorEventSource().poll() == []


def test_metrics_provider_is_a_metrics_provider():
    assert isinstance(SimulatedMetricsProvider(), MetricsProvider)


def test_metrics_provider_reads_a_dict():
    m = SimulatedMetricsProvider().read()
    assert "cpu_percent" in m
    assert "memory_percent" in m
