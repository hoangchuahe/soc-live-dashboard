from __future__ import annotations

import socket
from datetime import UTC, datetime
from typing import Any

from ..ecs import make_event
from .base import SourceStatus


def _import_psutil() -> Any | None:
    try:
        import psutil
    except Exception:
        return None
    return psutil


class NetConnSource:
    """Emits one ECS event per newly-established outbound connection."""

    name = "host.network"
    dataset = "host.network"
    interval_seconds = 5.0

    def __init__(self, psutil_module: Any | None = None, host_name: str | None = None) -> None:
        self._psutil = psutil_module if psutil_module is not None else _import_psutil()
        self._host = host_name or socket.gethostname()
        self._seen: set[tuple[str, int, int | None]] = set()
        self._primed = False

    def preflight(self) -> SourceStatus:
        if self._psutil is None:
            return SourceStatus(name=self.name, available=False, detail="psutil not installed")
        return SourceStatus(name=self.name, available=True, detail="ok")

    def poll(self) -> list[dict]:
        if self._psutil is None:
            return []
        conns = self._psutil.net_connections(kind="inet")
        current: set[tuple[str, int, int | None]] = set()
        events: list[dict] = []

        for c in conns:
            if c.status != "ESTABLISHED" or not c.raddr:
                continue
            key = (c.raddr.ip, c.raddr.port, c.pid)
            current.add(key)
            if not self._primed or key in self._seen:
                continue
            events.append(self._to_ecs(c))

        self._seen = current
        self._primed = True
        return events

    def _proc_name(self, pid: int | None) -> str | None:
        if pid is None or self._psutil is None:
            return None
        try:
            return self._psutil.Process(pid).name()
        except Exception:
            return None

    def _to_ecs(self, c: Any) -> dict:
        local_ip = getattr(c.laddr, "ip", None)
        return make_event(
            event_id=f"net-{c.raddr.ip}-{c.raddr.port}-{int(datetime.now(UTC).timestamp() * 1000)}",
            timestamp=datetime.now(UTC).isoformat(),
            category="network",
            action="network_connection",
            outcome="unknown",
            severity="low",
            module="netflow",
            message=f"Connection {local_ip} -> {c.raddr.ip}:{c.raddr.port}",
            source_ip=local_ip,
            destination_ip=c.raddr.ip,
            host_name=self._host,
            process_name=self._proc_name(c.pid),
            dataset=self.dataset,
        )
