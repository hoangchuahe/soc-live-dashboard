"""Source/MetricsProvider protocols + SourceStatus."""

from __future__ import annotations

from app.sources.base import MetricsProvider, Source, SourceStatus


class _DummySource:
    name = "x.dummy"
    dataset = "x.dummy"
    interval_seconds = 1.0

    def preflight(self) -> SourceStatus:
        return SourceStatus(name=self.name, available=True)

    def poll(self) -> list[dict]:
        return []


class _DummyMetrics:
    name = "host.metrics"

    def preflight(self) -> SourceStatus:
        return SourceStatus(name=self.name, available=True)

    def read(self) -> dict:
        return {}


def test_source_status_defaults():
    st = SourceStatus(name="a", available=False)
    assert st.detail == "unavailable"
    assert st.name == "a"


def test_dummy_satisfies_source_protocol():
    assert isinstance(_DummySource(), Source)


def test_dummy_satisfies_metrics_protocol():
    assert isinstance(_DummyMetrics(), MetricsProvider)
