"""
Sigma-style YAML rule loader.

Loads detection rules from `backend/detections/*.yml` and parses them into
`Rule` objects. Format is a pragmatic subset of the Sigma specification:
https://github.com/SigmaHQ/sigma/wiki/Specification
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DETECTIONS_DIR = Path(__file__).resolve().parents[2] / "detections"


@dataclass
class Threshold:
    by: str               # ECS field path to group by (e.g. "source.ip")
    count: int            # number of matches to fire
    window_seconds: int   # rolling window length


@dataclass
class Rule:
    id: str
    title: str
    description: str
    severity: str
    risk_weight: int
    selection: dict[str, Any]               # ECS field → expected value
    threshold: Threshold | None
    tactic: str | None
    technique_id: str | None
    technique_name: str | None
    fire_count: int = 0
    last_fired: str | None = None

    def matches_selection(self, event: dict[str, Any]) -> bool:
        """Check whether `event` satisfies all selection criteria."""
        for path, expected in self.selection.items():
            actual = _resolve(event, path)
            if actual != expected:
                return False
        return True


def _resolve(obj: dict[str, Any], dotted: str) -> Any:
    """Walk a dotted ECS field path (`source.ip` → obj['source']['ip'])."""
    cur: Any = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur


def load_rules(directory: Path | None = None) -> list[Rule]:
    directory = directory or DETECTIONS_DIR
    if not directory.exists():
        return []

    rules: list[Rule] = []
    for path in sorted(directory.glob("*.yml")):
        with path.open("r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        det = doc.get("detection", {})
        sel = det.get("selection", {}) or {}

        thr_raw = det.get("threshold")
        threshold = None
        if thr_raw:
            threshold = Threshold(
                by=thr_raw["by"],
                count=int(thr_raw["count"]),
                window_seconds=int(thr_raw["window_seconds"]),
            )

        mitre = doc.get("mitre", {}) or {}

        rules.append(Rule(
            id=doc["id"],
            title=doc["title"],
            description=doc.get("description", "").strip(),
            severity=doc.get("severity", "medium"),
            risk_weight=int(doc.get("risk_weight", 10)),
            selection=sel,
            threshold=threshold,
            tactic=mitre.get("tactic"),
            technique_id=mitre.get("technique_id"),
            technique_name=mitre.get("technique_name"),
        ))

    return rules
