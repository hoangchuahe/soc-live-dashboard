"""Parser tests — AST shapes for happy paths, errors with positions."""

from __future__ import annotations

import pytest

from app.query.parser import (
    And,
    Compare,
    Not,
    Or,
    ParseError,
    parse,
)


class TestSimple:
    def test_single_compare(self):
        ast = parse('source.ip:"10.0.0.5"')
        assert ast == Compare(field=("source", "ip"), op=":", value="10.0.0.5")

    def test_bareword_value(self):
        # event.severity:high — bareword 'high' is a string value
        ast = parse("event.severity:high")
        assert ast == Compare(field=("event", "severity"), op=":", value="high")

    def test_numeric_value(self):
        ast = parse("risk_score>=50")
        assert ast == Compare(field=("risk_score",), op=">=", value=50)

    def test_float_value(self):
        ast = parse("cpu.percent>2.5")
        assert ast == Compare(field=("cpu", "percent"), op=">", value=2.5)


class TestBoolean:
    def test_and(self):
        ast = parse("a:1 AND b:2")
        assert ast == And(
            Compare(("a",), ":", 1),
            Compare(("b",), ":", 2),
        )

    def test_or(self):
        ast = parse("a:1 OR b:2")
        assert ast == Or(
            Compare(("a",), ":", 1),
            Compare(("b",), ":", 2),
        )

    def test_not(self):
        ast = parse("NOT a:1")
        assert ast == Not(Compare(("a",), ":", 1))

    def test_and_or_precedence(self):
        # 'a OR b AND c' must parse as 'a OR (b AND c)'
        ast = parse("a:1 OR b:2 AND c:3")
        assert ast == Or(
            Compare(("a",), ":", 1),
            And(
                Compare(("b",), ":", 2),
                Compare(("c",), ":", 3),
            ),
        )

    def test_parens_override_precedence(self):
        ast = parse("(a:1 OR b:2) AND c:3")
        assert ast == And(
            Or(Compare(("a",), ":", 1), Compare(("b",), ":", 2)),
            Compare(("c",), ":", 3),
        )

    def test_not_binds_tighter_than_and(self):
        ast = parse("NOT a:1 AND b:2")
        assert ast == And(Not(Compare(("a",), ":", 1)), Compare(("b",), ":", 2))


class TestRealisticQueries:
    def test_full_example_from_spec(self):
        ast = parse('source.ip:"10.0.0.5" AND NOT event.outcome:success')
        assert ast == And(
            Compare(("source", "ip"), ":", "10.0.0.5"),
            Not(Compare(("event", "outcome"), ":", "success")),
        )


class TestParseErrors:
    def test_empty_input(self):
        with pytest.raises(ParseError) as exc:
            parse("")
        assert exc.value.position == 0

    def test_whitespace_only(self):
        with pytest.raises(ParseError):
            parse("   ")

    def test_dangling_and(self):
        with pytest.raises(ParseError) as exc:
            parse("a:1 AND")
        # error should be at or after the AND
        assert exc.value.position >= 4

    def test_unclosed_paren(self):
        with pytest.raises(ParseError):
            parse("(a:1")

    def test_missing_operator(self):
        with pytest.raises(ParseError):
            parse("a:1 b:2")

    def test_missing_value(self):
        with pytest.raises(ParseError):
            parse("a:")

    def test_missing_field(self):
        with pytest.raises(ParseError):
            parse(':"x"')
