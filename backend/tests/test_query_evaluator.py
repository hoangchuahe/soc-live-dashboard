"""Evaluator tests — AST + event -> bool."""

from __future__ import annotations

import pytest

from app.query import evaluate, parse


def _event(**overrides) -> dict:
    base = {
        "@timestamp": "2026-05-17T10:00:00Z",
        "event": {"id": "e1", "kind": "event", "category": "authentication",
                  "severity": "high", "outcome": "failure"},
        "source": {"ip": "10.0.0.5"},
        "host": {"name": "WKS-01"},
        "risk_score": 42,
    }
    base.update(overrides)
    return base


class TestColonOperator:
    def test_string_substring_match(self):
        ast = parse('source.ip:"10.0"')
        assert evaluate(ast, _event()) is True

    def test_string_substring_no_match(self):
        ast = parse('source.ip:"99"')
        assert evaluate(ast, _event()) is False

    def test_string_case_insensitive(self):
        ast = parse("host.name:wks")
        assert evaluate(ast, _event()) is True

    def test_numeric_equality(self):
        ast = parse("risk_score:42")
        assert evaluate(ast, _event()) is True

    def test_numeric_inequality(self):
        ast = parse("risk_score:99")
        assert evaluate(ast, _event()) is False


class TestStrictEquality:
    def test_equals_strict_string(self):
        ast = parse('source.ip="10.0.0.5"')
        assert evaluate(ast, _event()) is True

    def test_equals_strict_string_no_substring(self):
        ast = parse('source.ip="10.0"')  # not equal, even though substring would match
        assert evaluate(ast, _event()) is False

    def test_not_equals(self):
        ast = parse('event.outcome!="success"')
        assert evaluate(ast, _event()) is True


class TestNumericComparison:
    @pytest.mark.parametrize("expr,expected", [
        ("risk_score>40", True),
        ("risk_score>42", False),
        ("risk_score>=42", True),
        ("risk_score<50", True),
        ("risk_score<=42", True),
        ("risk_score<10", False),
    ])
    def test_numeric_ops(self, expr, expected):
        assert evaluate(parse(expr), _event()) is expected


class TestBooleans:
    def test_and_both_true(self):
        ast = parse("event.severity:high AND event.category:authentication")
        assert evaluate(ast, _event()) is True

    def test_and_one_false(self):
        ast = parse("event.severity:high AND event.category:network")
        assert evaluate(ast, _event()) is False

    def test_or_one_true(self):
        ast = parse("event.severity:low OR event.severity:high")
        assert evaluate(ast, _event()) is True

    def test_not_inverts(self):
        ast = parse("NOT event.outcome:success")
        assert evaluate(ast, _event()) is True


class TestMissingFields:
    def test_missing_field_colon_is_false(self):
        ast = parse('user.name:"alice"')   # no user.name in event
        assert evaluate(ast, _event()) is False

    def test_missing_field_equals_is_false(self):
        ast = parse('user.name="alice"')
        assert evaluate(ast, _event()) is False

    def test_missing_field_not_equals_is_true(self):
        ast = parse('user.name!="alice"')
        assert evaluate(ast, _event()) is True

    def test_missing_field_numeric_is_false(self):
        ast = parse("unknown>10")
        assert evaluate(ast, _event()) is False


class TestNullIntermediate:
    def test_dotted_path_through_none(self):
        evt = _event(threat={"tactic": None})
        # threat.tactic.name should resolve to missing, not crash
        ast = parse('threat.tactic.name:"x"')
        assert evaluate(ast, evt) is False
