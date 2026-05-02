"""
Prometheus-style metrics.

Exposed via `GET /metrics` in plain text Prometheus exposition format.
Counters cover the operational health of the ingestion + detection pipeline,
which is the standard observability surface that SOC platforms expect.
"""

from __future__ import annotations

import time
from threading import Lock


class Counter:
    def __init__(self, name: str, help_text: str, labels: tuple[str, ...] = ()):
        self.name = name
        self.help = help_text
        self.label_names = labels
        self._values: dict[tuple[str, ...], float] = {}
        self._lock = Lock()

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = tuple(labels.get(n, "") for n in self.label_names)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def render(self) -> list[str]:
        out = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        if not self._values:
            out.append(f"{self.name} 0")
            return out
        for key, val in sorted(self._values.items()):
            if self.label_names:
                label_str = ",".join(f'{n}="{v}"' for n, v in zip(self.label_names, key))
                out.append(f"{self.name}{{{label_str}}} {val}")
            else:
                out.append(f"{self.name} {val}")
        return out


class Gauge:
    def __init__(self, name: str, help_text: str):
        self.name = name
        self.help = help_text
        self._value = 0.0

    def set(self, value: float) -> None:
        self._value = value

    def render(self) -> list[str]:
        return [
            f"# HELP {self.name} {self.help}",
            f"# TYPE {self.name} gauge",
            f"{self.name} {self._value}",
        ]


# ── Singletons ────────────────────────────────────────────────────────────────

events_ingested = Counter(
    "soc_events_ingested_total",
    "Total raw events ingested by the simulator/pipeline",
    ("category", "severity"),
)

detections_fired = Counter(
    "soc_detections_fired_total",
    "Total detection rules that fired",
    ("rule_id", "tactic"),
)

websocket_clients = Gauge(
    "soc_websocket_clients",
    "Currently connected WebSocket clients",
)

uptime_started_at = time.time()


def render() -> str:
    lines: list[str] = []
    for collector in (events_ingested, detections_fired, websocket_clients):
        lines.extend(collector.render())
    lines.append("# HELP soc_uptime_seconds Process uptime in seconds")
    lines.append("# TYPE soc_uptime_seconds gauge")
    lines.append(f"soc_uptime_seconds {time.time() - uptime_started_at:.0f}")
    return "\n".join(lines) + "\n"
