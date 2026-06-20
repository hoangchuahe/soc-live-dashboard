"""Correlation engine + loader tests."""

from __future__ import annotations

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
