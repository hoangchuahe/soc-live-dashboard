"""Lexer tests — tokens, positions, errors."""

from __future__ import annotations

import pytest

from app.query.lexer import Token, tokenize, LexError


def kinds(src: str) -> list[str]:
    return [t.kind for t in tokenize(src) if t.kind != "EOF"]


def values(src: str) -> list[object]:
    return [t.value for t in tokenize(src) if t.kind != "EOF"]


class TestSingleTokens:
    def test_ident(self):
        assert kinds("foo") == ["IDENT"]
        assert values("foo") == ["foo"]

    def test_dotted_ident_is_three_tokens(self):
        assert kinds("source.ip") == ["IDENT", "DOT", "IDENT"]

    def test_string(self):
        assert kinds('"hello"') == ["STRING"]
        assert values('"hello"') == ["hello"]

    def test_string_with_escape(self):
        assert values(r'"a\"b"') == ['a"b']

    def test_number_int(self):
        assert kinds("42") == ["NUMBER"]
        assert values("42") == [42]

    def test_number_float(self):
        assert values("3.14") == [3.14]

    def test_colon(self):
        assert kinds(":") == ["COLON"]

    @pytest.mark.parametrize("src,op", [
        ("=", "="), ("!=", "!="), (">", ">"), (">=", ">="), ("<", "<"), ("<=", "<="),
    ])
    def test_operators(self, src, op):
        toks = tokenize(src)
        assert toks[0].kind == "OP"
        assert toks[0].value == op

    def test_parens(self):
        assert kinds("()") == ["LPAREN", "RPAREN"]

    @pytest.mark.parametrize("src,kind", [
        ("and", "AND"), ("AND", "AND"), ("And", "AND"),
        ("or", "OR"), ("OR", "OR"),
        ("not", "NOT"), ("NOT", "NOT"),
    ])
    def test_keywords_case_insensitive(self, src, kind):
        assert kinds(src) == [kind]


class TestCompoundInput:
    def test_simple_compare(self):
        assert kinds('source.ip:"x"') == ["IDENT", "DOT", "IDENT", "COLON", "STRING"]

    def test_full_query(self):
        src = 'source.ip:"10.0.0.5" AND NOT event.outcome:success'
        assert kinds(src) == [
            "IDENT", "DOT", "IDENT", "COLON", "STRING",
            "AND", "NOT",
            "IDENT", "DOT", "IDENT", "COLON", "IDENT",
        ]

    def test_whitespace_is_skipped(self):
        assert kinds("  foo   :   42  ") == ["IDENT", "COLON", "NUMBER"]

    def test_eof_is_emitted_last(self):
        toks = tokenize("foo")
        assert toks[-1].kind == "EOF"


class TestPositions:
    def test_position_is_column_index(self):
        toks = tokenize('a AND "b"')
        # 'a' at col 0, AND at col 2, '"b"' at col 6
        assert toks[0].position == 0
        assert toks[1].position == 2
        assert toks[2].position == 6


class TestLexErrors:
    def test_unterminated_string(self):
        with pytest.raises(LexError) as exc:
            tokenize('"oops')
        assert exc.value.position == 0

    def test_unexpected_character(self):
        with pytest.raises(LexError) as exc:
            tokenize("foo @ bar")
        assert exc.value.position == 4
