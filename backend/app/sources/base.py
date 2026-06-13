from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class SourceStatus:
    """Result of a source's preflight check, surfaced via /health."""

    name: str
    available: bool
    detail: str = "unavailable"


@runtime_checkable
class Source(Protocol):
    """Produces ECS event dicts from one real-world signal.

    `poll()` is synchronous and may block (file/OS calls); the Producer runs it
    in a worker thread via asyncio.to_thread, so implementations must NOT be
    coroutines.
    """

    name: str               # stable key, e.g. "host.network"
    dataset: str            # ECS event.dataset value
    interval_seconds: float

    def preflight(self) -> SourceStatus: ...

    def poll(self) -> list[dict]: ...


@runtime_checkable
class MetricsProvider(Protocol):
    """Produces the stats-bar metrics dict for each WebSocket frame."""

    name: str

    def preflight(self) -> SourceStatus: ...

    def read(self) -> dict: ...
