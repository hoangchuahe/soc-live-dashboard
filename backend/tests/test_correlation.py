"""Correlation engine + loader tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.detection.correlation import (
    CorrelationRule,
    load_correlation_rules,
)


def _write(tmp_path, name, body):
    (tmp_path / name).write_text(body, encoding="utf-8")


def test_loader_parses_valid_rule(tmp_path):
    _write(tmp_path, "good.yml",
        "id: corr-1\n"
        "title: Chain\n"
        "correlation:\n"
        "  type: temporal_ordered\n"
        "  rules: [rule-0001-auth-brute, rule-0003-lateral-rdp]\n"
        "  group-by: host.name\n"
        "  timespan: 600\n"
        "severity: critical\n"
        "risk_weight: 60\n",
    )
    rules = load_correlation_rules(
        {"rule-0001-auth-brute", "rule-0003-lateral-rdp"}, directory=tmp_path
    )
    assert len(rules) == 1
    r = rules[0]
    assert isinstance(r, CorrelationRule)
    assert r.id == "corr-1"
    assert r.stage_rule_ids == ["rule-0001-auth-brute", "rule-0003-lateral-rdp"]
    assert r.group_by == "host.name"
    assert r.timespan == 600
    assert r.severity == "critical"
    assert r.risk_weight == 60


def test_loader_skips_unknown_base_rule(tmp_path):
    _write(tmp_path, "bad.yml",
        "id: corr-bad\n"
        "title: Bad\n"
        "correlation:\n"
        "  type: temporal_ordered\n"
        "  rules: [rule-0001-auth-brute, rule-9999-nope]\n"
        "  group-by: host.name\n"
        "  timespan: 600\n",
    )
    rules = load_correlation_rules({"rule-0001-auth-brute"}, directory=tmp_path)
    assert rules == []


def test_loader_skips_boolean_timespan(tmp_path):
    _write(tmp_path, "booltimespan.yml",
        "id: corr-b\ntitle: B\ncorrelation:\n  type: temporal_ordered\n"
        "  rules: [rule-0001-auth-brute]\n  group-by: host.name\n  timespan: true\n",
    )
    rules = load_correlation_rules({"rule-0001-auth-brute"}, directory=tmp_path)
    assert rules == []


def test_loader_skips_missing_group_by(tmp_path):
    _write(tmp_path, "nogroup.yml",
        "id: corr-g\ntitle: G\ncorrelation:\n  type: temporal_ordered\n"
        "  rules: [rule-0001-auth-brute]\n  timespan: 600\n",
    )
    rules = load_correlation_rules({"rule-0001-auth-brute"}, directory=tmp_path)
    assert rules == []


def test_loader_skips_bad_type_and_timespan(tmp_path):
    _write(tmp_path, "type.yml",
        "id: corr-t\ntitle: T\ncorrelation:\n  type: nope\n"
        "  rules: [rule-0001-auth-brute]\n  group-by: host.name\n  timespan: 600\n",
    )
    _write(tmp_path, "span.yml",
        "id: corr-s\ntitle: S\ncorrelation:\n  type: temporal_ordered\n"
        "  rules: [rule-0001-auth-brute]\n  group-by: host.name\n  timespan: 0\n",
    )
    rules = load_correlation_rules({"rule-0001-auth-brute"}, directory=tmp_path)
    assert rules == []


from app.detection.correlation import CorrelationEngine  # noqa: E402
from app.detection.engine import Detection  # noqa: E402
from app.risk import RiskTracker  # noqa: E402


def _corr_rule(timespan=600):
    return CorrelationRule(
        id="corr-test", title="Test Chain", description="",
        type="temporal_ordered",
        stage_rule_ids=["rule-A", "rule-B", "rule-C"],
        group_by="host.name", timespan=timespan,
        severity="critical", risk_weight=60,
    )


def _ev(host="HOST-X"):
    return {"host": {"name": host}, "event": {"id": "e1"}}


def _bd(rule_id):
    return Detection(
        rule_id=rule_id, rule_title=rule_id, severity="high",
        timestamp=datetime.now(UTC).isoformat(), entity="x",
        technique_id=None, technique_name=None, tactic=None,
        triggering_event_id="e1", matched_count=1, message="m",
    )


def test_ordered_chain_fires_once():
    risk = RiskTracker()
    eng = CorrelationEngine([_corr_rule()], risk)
    assert eng.ingest(_ev(), [_bd("rule-A")]) == []
    assert eng.ingest(_ev(), [_bd("rule-B")]) == []
    out = eng.ingest(_ev(), [_bd("rule-C")])
    assert len(out) == 1
    assert out[0].rule_id == "corr-test"
    assert out[0].entity == "HOST-X"
    assert [s["rule_id"] for s in out[0].stages] == ["rule-A", "rule-B", "rule-C"]


def test_out_of_order_does_not_fire():
    eng = CorrelationEngine([_corr_rule()], RiskTracker())
    eng.ingest(_ev(), [_bd("rule-A")])
    assert eng.ingest(_ev(), [_bd("rule-C")]) == []


def test_timespan_exceeded_does_not_fire():
    clk = {"t": 1000.0}
    eng = CorrelationEngine([_corr_rule(timespan=300)], RiskTracker(), clock=lambda: clk["t"])
    eng.ingest(_ev(), [_bd("rule-A")])
    clk["t"] = 1000.0 + 301
    eng.ingest(_ev(), [_bd("rule-B")])   # expired -> sequence dropped
    clk["t"] = 1000.0 + 302
    assert eng.ingest(_ev(), [_bd("rule-C")]) == []


def test_different_group_does_not_fire():
    eng = CorrelationEngine([_corr_rule()], RiskTracker())
    eng.ingest(_ev("HOST-X"), [_bd("rule-A")])
    eng.ingest(_ev("HOST-Y"), [_bd("rule-B")])   # wrong host -> no advance on X
    assert eng.ingest(_ev("HOST-X"), [_bd("rule-C")]) == []


def test_no_refire_after_completion():
    eng = CorrelationEngine([_corr_rule()], RiskTracker())
    eng.ingest(_ev(), [_bd("rule-A")])
    eng.ingest(_ev(), [_bd("rule-B")])
    assert len(eng.ingest(_ev(), [_bd("rule-C")])) == 1
    assert eng.ingest(_ev(), [_bd("rule-C")]) == []   # sequence cleared


def test_missing_group_field_skips():
    eng = CorrelationEngine([_corr_rule()], RiskTracker())
    assert eng.ingest({"event": {"id": "e"}}, [_bd("rule-A")]) == []


def test_completion_bumps_entity_risk():
    risk = RiskTracker()
    eng = CorrelationEngine([_corr_rule()], risk)
    eng.ingest(_ev(), [_bd("rule-A")])
    eng.ingest(_ev(), [_bd("rule-B")])
    eng.ingest(_ev(), [_bd("rule-C")])
    top = risk.top(5)
    assert top and top[0]["name"] == "HOST-X"
    assert top[0]["score"] >= 59  # ~60 minus tiny decay


def test_campaign_director_emits_ordered_chain():
    from app.simulator import CampaignDirector

    director = CampaignDirector(start_probability=1.0)
    batches = [director.poll() for _ in range(4)]

    # Stage 1 is a burst of >=5 brute-force events (to trip the threshold rule).
    assert len(batches[0]) >= 5
    actions = [b[0]["event"]["action"] for b in batches]
    assert actions == ["auth_failure", "lateral_movement", "beacon", "anomaly"]

    # Every event in the campaign shares ONE host (the join key).
    hosts = {ev["host"]["name"] for batch in batches for ev in batch}
    assert len(hosts) == 1


def test_campaign_produces_one_correlated_detection():
    """The shipped campaign, fed through the real engine + correlation rule,
    yields exactly one multi-stage intrusion alert for the victim host."""
    from app.detection import DetectionEngine, load_rules
    from app.detection.correlation import CorrelationEngine, load_correlation_rules
    from app.simulator import CampaignDirector

    risk = RiskTracker()
    engine = DetectionEngine(load_rules(), risk)
    corr = CorrelationEngine(
        load_correlation_rules({r.id for r in engine.rules}), risk
    )
    director = CampaignDirector(start_probability=1.0)

    correlated = []
    for _ in range(4):                       # 4 stages = 4 polls drain one campaign
        for ev in director.poll():
            correlated += corr.ingest(ev, engine.evaluate(ev))

    multistage = [c for c in correlated if c.rule_id == "corr-0001-multistage-intrusion"]
    assert len(multistage) == 1
    assert [s["rule_id"] for s in multistage[0].stages] == [
        "rule-0001-auth-brute",
        "rule-0003-lateral-rdp",
        "rule-0004-c2-beacon",
        "rule-0006-exfil-volume",
    ]
