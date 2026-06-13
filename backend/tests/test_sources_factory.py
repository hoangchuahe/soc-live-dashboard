"""build_sources / build_metrics_provider by SOC_MODE."""

from __future__ import annotations

from app.sources import build_metrics_provider, build_sources
from app.sources.metrics_source import PsutilMetricsProvider
from app.sources.simulator_source import SimulatedMetricsProvider, SimulatorEventSource


def test_demo_mode_uses_simulator_only():
    sources, statuses = build_sources("demo")
    names = {s.name for s in sources}
    assert names == {"simulator.attack"}
    assert any(isinstance(s, SimulatorEventSource) for s in sources)


def test_demo_mode_metrics_are_simulated():
    assert isinstance(build_metrics_provider("demo"), SimulatedMetricsProvider)


def test_live_mode_excludes_simulator():
    sources, statuses = build_sources("live")
    assert "simulator.attack" not in {s.name for s in sources}


def test_blend_mode_includes_simulator():
    sources, statuses = build_sources("blend")
    assert "simulator.attack" in {s.name for s in sources}


def test_live_mode_metrics_are_psutil():
    assert isinstance(build_metrics_provider("live"), PsutilMetricsProvider)


def test_statuses_reported_for_real_sources():
    _, statuses = build_sources("live")
    # NetConn/Process/WinEvent each report a status (available or not)
    names = {st.name for st in statuses}
    assert {"host.network", "host.process", "windows.security"} <= names


def test_only_available_sources_are_active():
    sources, statuses = build_sources("live")
    active = {s.name for s in sources}
    for st in statuses:
        if not st.available:
            assert st.name not in active
