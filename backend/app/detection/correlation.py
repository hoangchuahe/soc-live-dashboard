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

from dataclasses import dataclass
from pathlib import Path

import yaml

from .loader import DETECTIONS_DIR

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
