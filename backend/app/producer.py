from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from . import metrics
from .detection import CorrelationEngine, DetectionEngine
from .hub import ConnectionHub
from .sources.base import MetricsProvider, Source

_AsyncSink = Callable[[dict], Awaitable[Any]]


async def _default_noop(_event: dict) -> None:
    return None


class Producer:
    """Single background loop: poll due sources -> detect -> buffer -> broadcast."""

    # consecutive failed polls before a source is reported "degraded" via /health
    DEGRADED_AFTER = 3

    def __init__(
        self,
        *,
        sources: list[Source],
        metrics_provider: MetricsProvider,
        engine: DetectionEngine,
        hub: ConnectionHub,
        correlation_engine: CorrelationEngine | None = None,
        event_buffer: deque[dict],
        alert_buffer: deque[dict],
        persist_event: _AsyncSink = _default_noop,
        index_event: _AsyncSink = _default_noop,
        create_alert_lifecycle: Callable[[str], Awaitable[Any]] | None = None,
        base_interval: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sources = list(sources)
        self._metrics = metrics_provider
        self._engine = engine
        self._correlation = correlation_engine
        self._hub = hub
        self._event_buffer = event_buffer
        self._alert_buffer = alert_buffer
        self._persist = persist_event
        self._index = index_event
        self._lifecycle = create_alert_lifecycle or _default_noop
        self._base_interval = base_interval
        self._clock = clock
        self._tick = 0
        self._next_due: dict[str, float] = {s.name: 0.0 for s in self._sources}
        self._consecutive_failures: dict[str, int] = {s.name: 0 for s in self._sources}
        self._running = False

    @property
    def event_buffer_len(self) -> int:
        return len(self._event_buffer)

    def source_status(self) -> dict[str, dict[str, int | bool]]:
        """Per-source runtime health for /health:
        {name: {"degraded": bool, "consecutive_failures": int}}.
        A source is degraded after DEGRADED_AFTER consecutive failed polls.
        """
        return {
            name: {
                "degraded": fails >= self.DEGRADED_AFTER,
                "consecutive_failures": fails,
            }
            for name, fails in self._consecutive_failures.items()
        }

    async def _poll_due_sources(self) -> list[dict]:
        now = self._clock()
        collected: list[dict] = []
        for src in self._sources:
            if now < self._next_due.get(src.name, 0.0):
                continue
            self._next_due[src.name] = now + src.interval_seconds
            try:
                events = await asyncio.to_thread(src.poll)
                self._consecutive_failures[src.name] = 0
            except Exception as exc:
                fails = self._consecutive_failures.get(src.name, 0) + 1
                self._consecutive_failures[src.name] = fails
                print(f"[producer] source {src.name} poll failed ({fails}x): {exc!r}")
                events = []
            collected.extend(events or [])
        return collected

    def _alerts_last_hour(self) -> int:
        # Approximate "alerts in the last hour" with the bounded alert ring buffer.
        # (Does NOT call self._clock(); the clock is consumed only by cadence gating,
        # so tests can count clock reads deterministically.)
        return len(self._alert_buffer)

    def _process_event(self, event: dict) -> list[dict]:
        self._event_buffer.append(event)
        ev = event.get("event", {})
        metrics.events_ingested.inc(
            category=ev.get("category", "unknown"),
            severity=ev.get("severity", "low"),
        )
        fired: list[dict] = []
        base_dets = self._engine.evaluate(event)
        for det in base_dets:
            alert = det.to_ecs()
            fired.append(alert)
            self._alert_buffer.append(alert)
            metrics.detections_fired.inc(rule_id=det.rule_id, tactic=det.tactic or "unknown")

        if self._correlation is not None:
            for cdet in self._correlation.ingest(event, base_dets):
                calert = cdet.to_ecs()
                fired.append(calert)
                self._alert_buffer.append(calert)
                metrics.detections_fired.inc(rule_id=cdet.rule_id, tactic="correlation")

        asyncio.create_task(self._persist(event))
        asyncio.create_task(self._index(event))
        for alert in fired:
            asyncio.create_task(self._persist(alert))
            asyncio.create_task(self._lifecycle(alert["event"]["id"]))
            asyncio.create_task(self._index(alert))
        return fired

    async def tick(self) -> list[dict]:
        self._tick += 1
        new_events = await self._poll_due_sources()
        current_metrics = dict(self._safe_metrics())
        current_metrics["alerts_last_hour"] = self._alerts_last_hour()

        frames: list[dict] = []
        if not new_events:
            frames.append({"tick": self._tick, "metrics": current_metrics,
                           "event": None, "alerts": []})
        else:
            for event in new_events:
                fired = self._process_event(event)
                frames.append({"tick": self._tick, "metrics": current_metrics,
                               "event": event, "alerts": fired})

        for frame in frames:
            await self._hub.broadcast(frame)
        return frames

    def _safe_metrics(self) -> dict:
        try:
            return self._metrics.read()
        except Exception as exc:
            print(f"[producer] metrics read failed: {exc!r}")
            return {}

    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            try:
                await self.tick()
            except Exception as exc:
                print(f"[producer] tick failed: {exc!r}")
            await asyncio.sleep(self._base_interval)

    def stop(self) -> None:
        self._running = False
