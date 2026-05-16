"""
Detection engine + Sigma rule loader tests.

Validates that:
  - YAML rules load and parse correctly
  - Selection criteria match ECS-shaped events
  - Sliding-window thresholds fire only when count is reached
  - Risk scores accumulate per entity
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from app.detection import DetectionEngine, load_rules
from app.detection.loader import Rule
from app.risk import RiskTracker

# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_event(category: str, action: str, outcome: str = "failure",
               source_ip: str = "1.2.3.4", host: str = "WKS-01") -> dict:
    return {
        "@timestamp": datetime.now(UTC).isoformat(),
        "event": {
            "id": f"evt-{int(time.time() * 1000)}",
            "kind": "event",
            "category": category,
            "action": action,
            "outcome": outcome,
            "severity": "high",
            "module": "winevent",
        },
        "source": {"ip": source_ip},
        "host":   {"name": host},
    }


@pytest.fixture
def engine() -> DetectionEngine:
    rules = load_rules()
    risk = RiskTracker()
    return DetectionEngine(rules, risk)


# ── Loader tests ──────────────────────────────────────────────────────────────

def test_loader_finds_all_rules():
    rules = load_rules()
    assert len(rules) >= 6, f"Expected ≥6 rules, found {len(rules)}"

    ids = {r.id for r in rules}
    assert "rule-0001-auth-brute" in ids
    assert "rule-0002-port-scan" in ids


def test_loader_parses_threshold():
    rules = {r.id: r for r in load_rules()}
    brute = rules["rule-0001-auth-brute"]

    assert brute.threshold is not None
    assert brute.threshold.by == "source.ip"
    assert brute.threshold.count == 5
    assert brute.threshold.window_seconds == 60


def test_loader_parses_mitre():
    rules = {r.id: r for r in load_rules()}
    brute = rules["rule-0001-auth-brute"]

    assert brute.tactic == "Credential Access"
    assert brute.technique_id == "T1110.001"
    assert brute.severity == "high"
    assert brute.risk_weight == 25


# ── Selection matching ────────────────────────────────────────────────────────

def test_selection_matches_correctly():
    rule = Rule(
        id="test-1", title="t", description="", severity="low", risk_weight=1,
        selection={"event.category": "authentication", "event.outcome": "failure"},
        threshold=None, tactic=None, technique_id=None, technique_name=None,
    )

    assert rule.matches_selection(make_event("authentication", "auth_failure"))
    assert not rule.matches_selection(make_event("network", "scan"))
    assert not rule.matches_selection(make_event("authentication", "auth_failure", outcome="success"))


# ── Threshold semantics ───────────────────────────────────────────────────────

def test_threshold_does_not_fire_below_count(engine: DetectionEngine):
    """4 failed auths from same IP shouldn't fire (rule needs 5)."""
    for _ in range(4):
        detections = engine.evaluate(make_event("authentication", "auth_failure", source_ip="9.9.9.9"))
        # the auth_brute rule should NOT have fired yet
        brute_fired = [d for d in detections if d.rule_id == "rule-0001-auth-brute"]
        assert not brute_fired


def test_threshold_fires_at_count(engine: DetectionEngine):
    """5 failed auths from same IP should fire the brute-force rule."""
    for _ in range(5):
        detections = engine.evaluate(make_event("authentication", "auth_failure", source_ip="9.9.9.9"))

    brute_fired = [d for d in detections if d.rule_id == "rule-0001-auth-brute"]
    assert len(brute_fired) == 1
    assert brute_fired[0].entity == "9.9.9.9"
    assert brute_fired[0].matched_count >= 5


def test_threshold_keyed_per_entity(engine: DetectionEngine):
    """5 events split across 2 IPs should NOT fire (each entity below threshold)."""
    for _ in range(3):
        engine.evaluate(make_event("authentication", "auth_failure", source_ip="1.1.1.1"))
    for _ in range(2):
        detections = engine.evaluate(make_event("authentication", "auth_failure", source_ip="2.2.2.2"))

    brute_fired = [d for d in detections if d.rule_id == "rule-0001-auth-brute"]
    assert not brute_fired


# ── Non-threshold rules ───────────────────────────────────────────────────────

def test_lateral_movement_fires_immediately(engine: DetectionEngine):
    """Rules without thresholds should fire on first match."""
    detections = engine.evaluate(make_event("authentication", "lateral_movement", outcome="success"))

    lateral = [d for d in detections if d.rule_id == "rule-0003-lateral-rdp"]
    assert len(lateral) == 1
    assert lateral[0].severity == "high"


# ── Risk scoring ──────────────────────────────────────────────────────────────

def test_risk_score_accumulates():
    risk = RiskTracker()
    risk.bump("WKS-001", 10, "rule-A")
    risk.bump("WKS-001", 15, "rule-B")

    top = risk.top(5)
    assert top[0]["name"] == "WKS-001"
    assert top[0]["score"] >= 24  # ~25 minus tiny decay


def test_risk_score_per_entity():
    risk = RiskTracker()
    risk.bump("HOST-A", 30, "r1")
    risk.bump("HOST-B", 5,  "r1")

    top = risk.top(5)
    assert top[0]["name"] == "HOST-A"
    assert top[1]["name"] == "HOST-B"


def test_risk_decay_brings_score_down():
    risk = RiskTracker()
    risk.bump("HOST-X", 100, "r1")

    # Force the entity's last_updated far into the past
    ent = risk._entities["HOST-X"]
    ent.last_updated = time.time() - (3 * 30 * 60)  # 3 half-lives

    top = risk.top(5)
    # 100 * (0.5^3) = 12.5
    assert top[0]["score"] < 20
