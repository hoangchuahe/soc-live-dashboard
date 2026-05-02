"""
Stateful detection engine.

Maintains per-rule sliding-window counters keyed by the rule's `threshold.by`
field (typically `source.ip` or `host.name`). When a window crosses the
threshold a `Detection` is emitted and the rule's risk weight is added to
the entity's risk score via the RiskTracker.

This pattern mirrors Splunk's Risk-Based Alerting and Elastic's threshold
detection rules. It is *not* distributed — for horizontal scale the state
would move into Redis or a dedicated stream processor (Flink, Bytewax).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .loader import Rule, _resolve
from ..risk import RiskTracker


@dataclass
class Detection:
    """A fired detection — derived event with `event.kind = 'alert'` semantics."""

    rule_id: str
    rule_title: str
    severity: str
    timestamp: str
    entity: str          # the value of the rule's `threshold.by` field
    technique_id: str | None
    technique_name: str | None
    tactic: str | None
    triggering_event_id: str
    matched_count: int
    message: str

    def to_ecs(self) -> dict[str, Any]:
        """Serialise as an ECS event with `event.kind = alert`."""
        return {
            "@timestamp": self.timestamp,
            "event": {
                "id": f"alert-{self.rule_id}-{int(time.time() * 1000)}",
                "kind": "alert",
                "category": "detection",
                "severity": self.severity,
                "outcome": "success",
            },
            "rule": {
                "id": self.rule_id,
                "name": self.rule_title,
            },
            "threat": {
                "tactic":    {"name": self.tactic} if self.tactic else None,
                "technique": {"id": self.technique_id, "name": self.technique_name}
                             if self.technique_id else None,
            },
            "entity": self.entity,
            "matched_count": self.matched_count,
            "triggering_event_id": self.triggering_event_id,
            "message": self.message,
        }


@dataclass
class _Window:
    """Per-(rule, entity) sliding window."""
    timestamps: deque[float] = field(default_factory=deque)


class DetectionEngine:
    def __init__(self, rules: list[Rule], risk: RiskTracker):
        self.rules = rules
        self.risk = risk
        self._windows: dict[tuple[str, str], _Window] = defaultdict(_Window)

    def evaluate(self, event: dict[str, Any]) -> list[Detection]:
        """Run every rule against `event`. Returns 0+ `Detection`s."""
        fired: list[Detection] = []
        now = time.time()

        for rule in self.rules:
            if not rule.matches_selection(event):
                continue

            if rule.threshold:
                entity = _resolve(event, rule.threshold.by)
                if entity is None:
                    continue

                key = (rule.id, str(entity))
                win = self._windows[key]

                # Drop timestamps outside the window
                cutoff = now - rule.threshold.window_seconds
                while win.timestamps and win.timestamps[0] < cutoff:
                    win.timestamps.popleft()

                win.timestamps.append(now)

                if len(win.timestamps) >= rule.threshold.count:
                    fired.append(self._make_detection(rule, event, str(entity), len(win.timestamps)))
                    # reset so we don't re-fire on every subsequent event in the window
                    win.timestamps.clear()
            else:
                # no threshold — fire immediately
                entity = _resolve(event, "source.ip") or _resolve(event, "host.name") or "unknown"
                fired.append(self._make_detection(rule, event, str(entity), 1))

        # Update entity risk scores for every fired detection
        for det in fired:
            rule = next(r for r in self.rules if r.id == det.rule_id)
            self.risk.bump(det.entity, rule.risk_weight, det.rule_id)
            rule.fire_count += 1
            rule.last_fired = det.timestamp

        return fired

    def _make_detection(self, rule: Rule, event: dict[str, Any], entity: str, count: int) -> Detection:
        msg = (
            f"{rule.title} — entity={entity}"
            + (f" (count={count} in {rule.threshold.window_seconds}s)" if rule.threshold else "")
        )
        return Detection(
            rule_id=rule.id,
            rule_title=rule.title,
            severity=rule.severity,
            timestamp=datetime.now(timezone.utc).isoformat(),
            entity=entity,
            technique_id=rule.technique_id,
            technique_name=rule.technique_name,
            tactic=rule.tactic,
            triggering_event_id=_resolve(event, "event.id") or "unknown",
            matched_count=count,
            message=msg,
        )

    def rule_summary(self) -> list[dict[str, Any]]:
        return [
            {
                "id": r.id,
                "title": r.title,
                "severity": r.severity,
                "tactic": r.tactic,
                "technique_id": r.technique_id,
                "fire_count": r.fire_count,
                "last_fired": r.last_fired,
                "has_threshold": r.threshold is not None,
            }
            for r in self.rules
        ]
