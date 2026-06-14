"""Producer: cadence gating, detection, buffering, broadcast."""

from __future__ import annotations

from collections import deque

from app.detection import DetectionEngine, load_rules
from app.producer import Producer
from app.risk import RiskTracker


class _FakeHub:
    def __init__(self):
        self.frames: list[dict] = []

    async def broadcast(self, frame: dict) -> None:
        self.frames.append(frame)


class _StaticSource:
    """Returns the given events every poll; records poll calls."""

    def __init__(self, name, events, interval=1.0):
        self.name = name
        self.dataset = name
        self.interval_seconds = interval
        self._events = events
        self.poll_count = 0

    def preflight(self):
        from app.sources.base import SourceStatus
        return SourceStatus(name=self.name, available=True, detail="ok")

    def poll(self):
        self.poll_count += 1
        return list(self._events)


class _Metrics:
    name = "host.metrics"

    def preflight(self):
        from app.sources.base import SourceStatus
        return SourceStatus(name=self.name, available=True, detail="ok")

    def read(self):
        return {"cpu_percent": 1.0, "alerts_last_hour": 0}


async def _noop(*_a, **_k):
    return None


def _make_producer(sources, *, clock):
    engine = DetectionEngine(load_rules(), RiskTracker())
    return Producer(
        sources=sources, metrics_provider=_Metrics(), engine=engine,
        hub=_FakeHub(), event_buffer=deque(maxlen=500), alert_buffer=deque(maxlen=200),
        persist_event=_noop, index_event=_noop, create_alert_lifecycle=_noop,
        clock=clock,
    )


def _auth_failure(ip="9.9.9.9"):
    return {
        "@timestamp": "2026-06-14T00:00:00Z",
        "event": {"id": "e1", "kind": "event", "category": "authentication",
                  "action": "auth_failure", "outcome": "failure", "severity": "high",
                  "module": "winevent"},
        "source": {"ip": ip},
        "host": {"name": "WKS-01"},
    }


async def test_tick_with_no_events_emits_metrics_frame():
    src = _StaticSource("s", [], interval=1.0)
    prod = _make_producer([src], clock=lambda: 1000.0)
    frames = await prod.tick()
    assert len(frames) == 1
    assert frames[0]["event"] is None
    assert frames[0]["metrics"]["cpu_percent"] == 1.0


async def test_tick_emits_one_frame_per_event_and_buffers():
    src = _StaticSource("s", [_auth_failure()], interval=1.0)
    prod = _make_producer([src], clock=lambda: 1000.0)
    frames = await prod.tick()
    assert len(frames) == 1
    assert frames[0]["event"]["event"]["category"] == "authentication"
    assert prod.event_buffer_len == 1


async def test_detection_fires_and_alert_buffered():
    # 5 auth failures from one IP in one tick -> brute-force rule fires once
    src = _StaticSource("s", [_auth_failure() for _ in range(5)], interval=1.0)
    prod = _make_producer([src], clock=lambda: 1000.0)
    frames = await prod.tick()
    all_alerts = [a for f in frames for a in f["alerts"]]
    assert any(a["rule"]["id"] == "rule-0001-auth-brute" for a in all_alerts)


async def test_source_not_polled_before_interval_elapses():
    times = iter([1000.0, 1000.5, 1002.0])   # tick1 @1000, tick2 @1000.5, tick3 @1002
    src = _StaticSource("s", [], interval=1.0)
    prod = _make_producer([src], clock=lambda: next(times))
    await prod.tick()    # t=1000  -> polled (due)
    await prod.tick()    # t=1000.5 -> NOT due yet (next due 1001)
    await prod.tick()    # t=1002  -> due again
    assert src.poll_count == 2


async def test_failing_source_does_not_break_tick():
    class _Boom(_StaticSource):
        def poll(self):
            raise RuntimeError("kaboom")

    boom = _Boom("boom", [], interval=1.0)
    prod = _make_producer([boom], clock=lambda: 1000.0)
    frames = await prod.tick()      # must not raise
    assert len(frames) == 1
    assert frames[0]["event"] is None


async def test_source_degrades_after_consecutive_failures():
    class _Boom(_StaticSource):
        def poll(self):
            self.poll_count += 1
            raise RuntimeError("kaboom")

    boom = _Boom("boom", [], interval=1.0)
    times = iter([1000.0, 1001.0, 1002.0, 1003.0])   # advance so the 1s source is due each tick
    prod = _make_producer([boom], clock=lambda: next(times))
    for _ in range(3):
        await prod.tick()
    status = prod.source_status()["boom"]
    assert status["consecutive_failures"] == 3
    assert status["degraded"] is True


async def test_degraded_source_recovers_on_success():
    class _Flaky(_StaticSource):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fail = True

        def poll(self):
            self.poll_count += 1
            if self.fail:
                raise RuntimeError("transient")
            return []

    flaky = _Flaky("flaky", [], interval=1.0)
    times = iter([1000.0, 1001.0, 1002.0, 1003.0, 1004.0])
    prod = _make_producer([flaky], clock=lambda: next(times))
    for _ in range(3):
        await prod.tick()
    assert prod.source_status()["flaky"]["degraded"] is True

    flaky.fail = False
    await prod.tick()                                # next poll succeeds
    assert prod.source_status()["flaky"]["degraded"] is False
    assert prod.source_status()["flaky"]["consecutive_failures"] == 0
