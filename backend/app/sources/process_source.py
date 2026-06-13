from __future__ import annotations

import socket
from datetime import UTC, datetime
from typing import Any

from ..ecs import make_event
from .base import SourceStatus

_ATTRS = ["pid", "name", "ppid", "cmdline", "create_time"]


def _import_psutil() -> Any | None:
    try:
        import psutil
    except Exception:
        return None
    return psutil


class ProcessSource:
    """Emits one ECS event per newly-started process."""

    name = "host.process"
    dataset = "host.process"
    interval_seconds = 5.0

    def __init__(self, psutil_module: Any | None = None, host_name: str | None = None) -> None:
        self._psutil = psutil_module if psutil_module is not None else _import_psutil()
        self._host = host_name or socket.gethostname()
        self._seen: set[int] = set()
        self._primed = False

    def preflight(self) -> SourceStatus:
        if self._psutil is None:
            return SourceStatus(name=self.name, available=False, detail="psutil not installed")
        return SourceStatus(name=self.name, available=True, detail="ok")

    def poll(self) -> list[dict]:
        if self._psutil is None:
            return []
        current: set[int] = set()
        events: list[dict] = []

        for proc in self._psutil.process_iter(_ATTRS):
            info = getattr(proc, "info", {}) or {}
            pid = info.get("pid")
            if pid is None:
                continue
            current.add(pid)
            if not self._primed or pid in self._seen:
                continue
            events.append(self._to_ecs(info))

        self._seen = current
        self._primed = True
        return events

    def _to_ecs(self, info: dict) -> dict:
        name = info.get("name") or f"pid:{info.get('pid')}"
        cmdline = info.get("cmdline") or []
        evt = make_event(
            event_id=f"proc-{info.get('pid')}-{int(datetime.now(UTC).timestamp() * 1000)}",
            timestamp=datetime.now(UTC).isoformat(),
            category="process",
            action="process_start",
            outcome="unknown",
            severity="low",
            module="psutil",
            message=f"Process started: {name} (pid={info.get('pid')})",
            host_name=self._host,
            process_name=name,
            dataset=self.dataset,
        )
        # enrich the process block with pid / parent / command line
        evt.setdefault("process", {"name": name})
        evt["process"]["pid"] = info.get("pid")
        evt["process"]["command_line"] = " ".join(str(a) for a in cmdline)
        if info.get("ppid") is not None:
            evt["process"]["parent"] = {"pid": info["ppid"]}
        return evt
