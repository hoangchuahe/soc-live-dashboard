"""
Correlation engine — multi-stage (temporal_ordered) detection over base detections.

Sits ABOVE the single-event DetectionEngine: base rules fire `Detection`s, and a
correlation rule (Sigma-correlation-style) recognises an ORDERED sequence of those
base fires for the same `group-by` entity within a `timespan`, emitting one
higher-severity `CorrelatedDetection`.

Join semantics: the group value is re-resolved from each base detection's
triggering EVENT (not from `Detection.entity`, which differs per base rule), so
stages keyed differently by their base rules still correlate on a common field
(e.g. `host.name`).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ..risk import RiskTracker
from .engine import Detection
from .loader import DETECTIONS_DIR, _resolve

CORRELATIONS_DIR = DETECTIONS_DIR / "correlations"


@dataclass
class CorrelationRule:
    id: str
    title: str
    description: str
    type: str
    stage_rule_ids: list[str]
    group_by: str
    timespan: int
    severity: str
    risk_weight: int
    fire_count: int = 0
    last_fired: str | None = None


def load_correlation_rules(
    base_rule_ids: set[str], directory: Path | None = None
) -> list[CorrelationRule]:
    """Load + validate correlation rules. Invalid rules are skipped + warned
    (fail-soft), never crashing the app."""
    directory = directory or CORRELATIONS_DIR
    if not directory.exists():
        return []

    rules: list[CorrelationRule] = []
    for path in sorted(directory.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        rid = doc.get("id", path.stem)
        corr = doc.get("correlation", {}) or {}
        ctype = corr.get("type")
        stage_ids = corr.get("rules") or []
        group_by = corr.get("group-by")
        timespan = corr.get("timespan")

        if ctype != "temporal_ordered":
            print(f"[correlation] skip {rid}: unsupported type {ctype!r}")
            continue
        if not stage_ids:
            print(f"[correlation] skip {rid}: empty 'rules'")
            continue
        if not group_by:
            print(f"[correlation] skip {rid}: missing 'group-by'")
            continue
        if isinstance(timespan, bool) or not isinstance(timespan, int) or timespan <= 0:
            print(f"[correlation] skip {rid}: bad 'timespan' {timespan!r}")
            continue
        unknown = [s for s in stage_ids if s not in base_rule_ids]
        if unknown:
            print(f"[correlation] skip {rid}: unknown base rules {unknown}")
            continue

        rules.append(CorrelationRule(
            id=rid,
            title=doc.get("title", rid),
            description=str(doc.get("description", "")).strip(),
            type=ctype,
            stage_rule_ids=list(stage_ids),
            group_by=group_by,
            timespan=int(timespan),
            severity=doc.get("severity", "high"),
            risk_weight=int(doc.get("risk_weight", 40)),
        ))
    return rules


@dataclass
class CorrelatedDetection:
    """A fired multi-stage correlation — serialises as an ECS alert."""

    rule_id: str
    rule_title: str
    severity: str
    timestamp: str
    entity: str                      # the group-by value (e.g. host name)
    stages: list[dict[str, Any]]     # ordered child-stage summaries
    message: str

    def to_ecs(self) -> dict[str, Any]:
        return {
            "@timestamp": self.timestamp,
            "event": {
                "id": f"corr-{self.rule_id}-{int(time.time() * 1000)}",
                "kind": "alert",
                "category": "detection",
                "severity": self.severity,
                "outcome": "success",
            },
            "rule": {"id": self.rule_id, "name": self.rule_title},
            "host": {"name": self.entity},   # v1 groups by host.name; surface it
            "entity": self.entity,
            "message": self.message,
            "correlation": {"rule_id": self.rule_id, "stages": self.stages},
        }


@dataclass
class _Seq:
    """In-progress sequence state for one (correlation rule, group value)."""
    stage_idx: int
    started_at: float
    stages: list[Detection] = field(default_factory=list)


class CorrelationEngine:
    def __init__(
        self,
        rules: list[CorrelationRule],
        risk: RiskTracker,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.rules = rules
        self.risk = risk
        self._clock = clock
        self._seqs: dict[tuple[str, str], _Seq] = {}

    def ingest(
        self, event: dict[str, Any], base_detections: list[Detection]
    ) -> list[CorrelatedDetection]:
        """Advance sequences with this event's base detections; return completed
        correlations. Defensive: never raises into the producer tick."""
        now = self._clock()
        out: list[CorrelatedDetection] = []

        for det in base_detections:
            for rule in self.rules:
                group = _resolve(event, rule.group_by)
                if group is None:
                    continue
                key = (rule.id, str(group))
                stages = rule.stage_rule_ids

                # First stage (re)starts the sequence for this (rule, group).
                if det.rule_id == stages[0]:
                    self._seqs[key] = _Seq(stage_idx=1, started_at=now, stages=[det])
                    if len(stages) == 1:
                        out.append(self._fire(rule, str(group), self._seqs.pop(key)))
                    continue

                seq = self._seqs.get(key)
                if seq is None:
                    continue
                if now - seq.started_at > rule.timespan:
                    del self._seqs[key]          # expired
                    continue
                if det.rule_id == stages[seq.stage_idx]:
                    seq.stages.append(det)
                    seq.stage_idx += 1
                    if seq.stage_idx == len(stages):
                        out.append(self._fire(rule, str(group), seq))
                        del self._seqs[key]       # re-fire suppression

        return out

    def _fire(self, rule: CorrelationRule, group: str, seq: _Seq) -> CorrelatedDetection:
        ts = datetime.now(UTC).isoformat()
        rule.fire_count += 1
        rule.last_fired = ts
        self.risk.bump(group, rule.risk_weight, rule.id)
        stage_dicts = [
            {
                "rule_id": d.rule_id,
                "title": d.rule_title,
                "triggering_event_id": d.triggering_event_id,
                "timestamp": d.timestamp,
                "technique_id": d.technique_id,
                "technique_name": d.technique_name,
                "tactic": d.tactic,
            }
            for d in seq.stages
        ]
        chain = " -> ".join(d.rule_title for d in seq.stages)
        return CorrelatedDetection(
            rule_id=rule.id,
            rule_title=rule.title,
            severity=rule.severity,
            timestamp=ts,
            entity=group,
            stages=stage_dicts,
            message=f"Multi-stage attack on {group}: {chain}",
        )

    def rule_summary(self) -> list[dict[str, Any]]:
        return [
            {
                "id": r.id,
                "title": r.title,
                "severity": r.severity,
                "stages": r.stage_rule_ids,
                "group_by": r.group_by,
                "timespan": r.timespan,
                "fire_count": r.fire_count,
                "last_fired": r.last_fired,
            }
            for r in self.rules
        ]
