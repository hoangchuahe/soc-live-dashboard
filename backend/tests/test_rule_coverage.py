"""Per-rule detection coverage — the data-driven equivalent of "a pytest job per
rule" (the maturity gap noted in docs/ARCHITECTURE.md).

Every shipped base rule must:
  * FIRE on a representative ("positive") event, and
  * stay SILENT on a near-miss ("negative") event.

A meta-test pins that every loaded rule has a coverage fixture, so adding a new
rule without a test turns the suite red. Threshold rules feed their sample
`repeat` times (>= the rule's count) so the sliding window trips.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from typing import Any

import pytest

from app.detection import DetectionEngine, load_rules
from app.risk import RiskTracker

_ids = itertools.count(1)


def _event(sample: dict[str, str], ip: str = "203.0.113.77") -> dict[str, Any]:
    """Build a fresh ECS event from a sample's category/action/outcome."""
    return {
        "@timestamp": datetime.now(UTC).isoformat(),
        "event": {
            "id": f"evt-{next(_ids)}",
            "kind": "event",
            "category": sample["category"],
            "action": sample.get("action", "noop"),
            "outcome": sample.get("outcome", "unknown"),
            "severity": "high",
            "module": "winevent",
        },
        "source": {"ip": ip},
        "host": {"name": "WKS-TEST-01"},
    }


# rule_id -> positive (must fire) + negative (must NOT fire) samples, and how many
# times to feed them (threshold rules need repeat >= their count).
RULE_SAMPLES: dict[str, dict[str, Any]] = {
    "rule-0001-auth-brute": {
        "positive": {"category": "authentication", "action": "auth_failure", "outcome": "failure"},
        "negative": {"category": "authentication", "action": "auth_failure", "outcome": "success"},
        "repeat": 5,
    },
    "rule-0002-port-scan": {
        "positive": {"category": "network", "action": "scan"},
        "negative": {"category": "network", "action": "connection"},
        "repeat": 3,
    },
    "rule-0003-lateral-rdp": {
        "positive": {"category": "authentication", "action": "lateral_movement", "outcome": "success"},
        "negative": {"category": "authentication", "action": "auth_failure", "outcome": "success"},
        "repeat": 1,
    },
    "rule-0004-c2-beacon": {
        "positive": {"category": "malware", "action": "beacon"},
        "negative": {"category": "network", "action": "connection"},
        "repeat": 1,
    },
    "rule-0005-policy-violation": {
        "positive": {"category": "configuration", "action": "policy_violation"},
        "negative": {"category": "configuration", "action": "config_change"},
        "repeat": 1,
    },
    "rule-0006-exfil-volume": {
        "positive": {"category": "network", "action": "anomaly"},
        "negative": {"category": "network", "action": "scan"},
        "repeat": 1,
    },
    "rule-0007-web-exploit": {
        "positive": {"category": "intrusion_detection", "action": "exploit"},
        "negative": {"category": "network", "action": "connection"},
        "repeat": 1,
    },
}


def _run(sample: dict[str, str], repeat: int) -> set[str]:
    """Feed `sample` `repeat` times through a fresh engine; return fired rule ids."""
    engine = DetectionEngine(load_rules(), RiskTracker())
    fired: list = []
    for _ in range(repeat):
        fired += engine.evaluate(_event(sample))
    return {d.rule_id for d in fired}


@pytest.mark.parametrize("rule_id", list(RULE_SAMPLES))
def test_rule_fires_on_positive_sample(rule_id: str):
    spec = RULE_SAMPLES[rule_id]
    fired = _run(spec["positive"], spec["repeat"])
    assert rule_id in fired, f"{rule_id} did not fire on its positive sample"


@pytest.mark.parametrize("rule_id", list(RULE_SAMPLES))
def test_rule_silent_on_negative_sample(rule_id: str):
    spec = RULE_SAMPLES[rule_id]
    fired = _run(spec["negative"], spec["repeat"])
    assert rule_id not in fired, f"{rule_id} fired on its negative (near-miss) sample"


def test_every_loaded_rule_has_coverage():
    loaded = {r.id for r in load_rules()}
    covered = set(RULE_SAMPLES)
    assert loaded == covered, (
        f"rules missing coverage: {sorted(loaded - covered)}; "
        f"stale fixtures: {sorted(covered - loaded)}"
    )
