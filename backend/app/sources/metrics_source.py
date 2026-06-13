from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

from .base import SourceStatus


def _import_psutil() -> Any | None:
    try:
        import psutil
    except Exception:
        return None
    return psutil


class PsutilMetricsProvider:
    """Real system metrics via psutil. Cross-platform; defensive per-field."""

    name = "host.metrics"

    def __init__(
        self,
        psutil_module: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._psutil = psutil_module if psutil_module is not None else _import_psutil()
        self._clock = clock
        self._prev_net: tuple[float, int, int] | None = None  # (t, sent, recv)

    def preflight(self) -> SourceStatus:
        if self._psutil is None:
            return SourceStatus(name=self.name, available=False, detail="psutil not installed")
        return SourceStatus(name=self.name, available=True, detail="ok")

    def _safe(self, fn: Callable[[], float], default: float = 0.0) -> float:
        try:
            return fn()
        except Exception:
            return default

    def read(self) -> dict:
        ps = self._psutil
        if ps is None:
            return _ZERO_METRICS.copy()

        cpu = self._safe(lambda: round(float(ps.cpu_percent(interval=None)), 1))
        mem = self._safe(lambda: round(float(ps.virtual_memory().percent), 1))
        disk = self._safe(lambda: round(float(ps.disk_usage(os.path.abspath(os.sep)).percent), 1))
        conns = int(self._safe(lambda: float(len(ps.net_connections(kind="inet")))))

        in_mbps, out_mbps = self._net_mbps()

        return {
            "cpu_percent": cpu,
            "memory_percent": mem,
            "disk_percent": disk,
            "network_in_mbps": in_mbps,
            "network_out_mbps": out_mbps,
            "active_connections": conns,
            "alerts_last_hour": 0,   # filled in by the Producer from the alert buffer
        }

    def _net_mbps(self) -> tuple[float, float]:
        ps = self._psutil
        try:
            io = ps.net_io_counters()
            now = self._clock()
            sent, recv = int(io.bytes_sent), int(io.bytes_recv)
        except Exception:
            return 0.0, 0.0

        if self._prev_net is None:
            self._prev_net = (now, sent, recv)
            return 0.0, 0.0

        prev_t, prev_sent, prev_recv = self._prev_net
        elapsed = now - prev_t
        self._prev_net = (now, sent, recv)
        if elapsed <= 0:
            return 0.0, 0.0

        out_mbps = round(((sent - prev_sent) * 8) / 1e6 / elapsed, 1)
        in_mbps = round(((recv - prev_recv) * 8) / 1e6 / elapsed, 1)
        return max(0.0, in_mbps), max(0.0, out_mbps)


_ZERO_METRICS = {
    "cpu_percent": 0.0, "memory_percent": 0.0, "disk_percent": 0.0,
    "network_in_mbps": 0.0, "network_out_mbps": 0.0,
    "active_connections": 0, "alerts_last_hour": 0,
}
