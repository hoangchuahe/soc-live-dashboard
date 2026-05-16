# Investigation Pivot + Query DSL — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small query language over ECS fields plus an alert-pivot drawer in the UI, so analysts can click an alert and immediately see every event from that entity in a recent time window.

**Architecture:** A hand-rolled lexer → recursive-descent parser → AST evaluator lives in a new `backend/app/query/` package. The existing `GET /api/search` is rewired to: parse the DSL → run the evaluator as a Python predicate over events streamed from SQLite (filtered by a time window). The previous ElasticSearch passthrough moves to `GET /api/search/es`. The frontend gains a right-side `SearchPanel` drawer and a "🔍 Pivot" button on each alert row.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async + aiosqlite, pytest. Frontend: React 18, TypeScript, Tailwind.

**Spec:** [docs/superpowers/specs/2026-05-17-investigation-pivot-and-query-dsl-design.md](../specs/2026-05-17-investigation-pivot-and-query-dsl-design.md)

---

## File Map

**New backend files:**
- `backend/app/query/__init__.py` — re-exports `parse`, `evaluate`, `ParseError`
- `backend/app/query/lexer.py` — token types + `tokenize(src) -> list[Token]`
- `backend/app/query/parser.py` — AST node dataclasses + recursive-descent `parse(src) -> Node`
- `backend/app/query/evaluator.py` — dotted-path lookup + `evaluate(node, event) -> bool`
- `backend/tests/test_query_lexer.py`
- `backend/tests/test_query_parser.py`
- `backend/tests/test_query_evaluator.py`
- `backend/tests/test_search_api.py`

**Modified backend files:**
- `backend/app/db.py` — add `search_events(predicate, from_ts, to_ts, limit)`
- `backend/app/main.py` — replace `/api/search` body; move ES passthrough to `/api/search/es`

**New frontend files:**
- `frontend/src/lib/timeRange.ts` — preset → `{from, to}` ISO helpers
- `frontend/src/components/SearchPanel.tsx` — drawer + input + results list

**Modified frontend files:**
- `frontend/src/components/AlertFeed.tsx` — add pivot button + `onPivot` prop
- `frontend/src/App.tsx` — mount `SearchPanel`, hold `pivotState`, read URL params

**Modified docs:**
- `README.md` — add "Querying events" section + breaking-change note about `/api/search`

---

## Task 1: Lexer

**Files:**
- Create: `backend/app/query/__init__.py`
- Create: `backend/app/query/lexer.py`
- Create: `backend/tests/test_query_lexer.py`

The lexer converts source text into a flat list of tokens, each with a position for error reporting. Token kinds: `IDENT`, `DOT`, `COLON`, `OP` (one of `=`, `!=`, `>`, `>=`, `<`, `<=`), `STRING`, `NUMBER`, `LPAREN`, `RPAREN`, `AND`, `OR`, `NOT`, `EOF`. Whitespace is skipped. Keywords (`AND`, `OR`, `NOT`) are case-insensitive but emitted upper-case.

- [ ] **Step 1: Create the empty package**

```python
# backend/app/query/__init__.py
"""Query DSL for ECS events — lexer, parser, evaluator."""
```

- [ ] **Step 2: Write the failing lexer tests**

```python
# backend/tests/test_query_lexer.py
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
```

- [ ] **Step 3: Run lexer tests — expect failure**

Run: `cd backend && pytest tests/test_query_lexer.py -v`
Expected: `ModuleNotFoundError: No module named 'app.query.lexer'` (or similar import error).

- [ ] **Step 4: Implement the lexer**

```python
# backend/app/query/lexer.py
"""Lexer for the query DSL.

Tokenises a query string into a flat list of (kind, value, position) tuples.
Position is the 0-based column where the token started, used for error reporting
in the parser layer above.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TokenKind = Literal[
    "IDENT", "DOT", "COLON", "OP", "STRING", "NUMBER",
    "LPAREN", "RPAREN", "AND", "OR", "NOT", "EOF",
]


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: object
    position: int


class LexError(ValueError):
    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} at position {position}")
        self.detail = message
        self.position = position


_KEYWORDS: dict[str, TokenKind] = {"and": "AND", "or": "OR", "not": "NOT"}
_TWO_CHAR_OPS = {"!=", ">=", "<="}
_ONE_CHAR_OPS = {"=", ">", "<"}


def tokenize(src: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]

        if ch.isspace():
            i += 1
            continue

        if ch == "(":
            tokens.append(Token("LPAREN", "(", i)); i += 1; continue
        if ch == ")":
            tokens.append(Token("RPAREN", ")", i)); i += 1; continue
        if ch == ":":
            tokens.append(Token("COLON", ":", i)); i += 1; continue
        if ch == ".":
            tokens.append(Token("DOT", ".", i)); i += 1; continue

        # Operators — try two-char first
        two = src[i : i + 2]
        if two in _TWO_CHAR_OPS:
            tokens.append(Token("OP", two, i)); i += 2; continue
        if ch in _ONE_CHAR_OPS:
            tokens.append(Token("OP", ch, i)); i += 1; continue

        # Strings
        if ch == '"':
            start = i
            i += 1
            buf: list[str] = []
            while i < n and src[i] != '"':
                if src[i] == "\\" and i + 1 < n:
                    buf.append(src[i + 1])
                    i += 2
                    continue
                buf.append(src[i])
                i += 1
            if i >= n:
                raise LexError("unterminated string literal", start)
            i += 1  # consume closing quote
            tokens.append(Token("STRING", "".join(buf), start))
            continue

        # Numbers
        if ch.isdigit():
            start = i
            while i < n and (src[i].isdigit() or src[i] == "."):
                i += 1
            text = src[start:i]
            value: float | int = float(text) if "." in text else int(text)
            tokens.append(Token("NUMBER", value, start))
            continue

        # Identifiers / keywords
        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (src[i].isalnum() or src[i] == "_"):
                i += 1
            text = src[start:i]
            kind = _KEYWORDS.get(text.lower())
            if kind:
                tokens.append(Token(kind, text.upper(), start))
            else:
                tokens.append(Token("IDENT", text, start))
            continue

        raise LexError(f"unexpected character {ch!r}", i)

    tokens.append(Token("EOF", None, n))
    return tokens
```

- [ ] **Step 5: Run lexer tests — expect pass**

Run: `cd backend && pytest tests/test_query_lexer.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/query/__init__.py backend/app/query/lexer.py backend/tests/test_query_lexer.py
git commit -m "feat(query): add lexer for the DSL"
```

---

## Task 2: Parser + AST

**Files:**
- Create: `backend/app/query/parser.py`
- Create: `backend/tests/test_query_parser.py`

Operator precedence (low → high): `OR` → `AND` → `NOT` → `comparison` / `( expr )`. Recursive-descent matches the grammar verbatim.

- [ ] **Step 1: Write the failing parser tests**

```python
# backend/tests/test_query_parser.py
"""Parser tests — AST shapes for happy paths, errors with positions."""

from __future__ import annotations

import pytest

from app.query.parser import (
    And, Or, Not, Compare, ParseError, parse,
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
```

- [ ] **Step 2: Run parser tests — expect failure**

Run: `cd backend && pytest tests/test_query_parser.py -v`
Expected: `ModuleNotFoundError: No module named 'app.query.parser'`.

- [ ] **Step 3: Implement the parser**

```python
# backend/app/query/parser.py
"""Recursive-descent parser for the query DSL.

Grammar (low to high precedence):

    expr     := or_expr
    or_expr  := and_expr ("OR" and_expr)*
    and_expr := not_expr ("AND" not_expr)*
    not_expr := "NOT"? atom
    atom     := comparison | "(" expr ")"
    compare  := field op value
    field    := IDENT ("." IDENT)*
    op       := ":" | "=" | "!=" | ">" | ">=" | "<" | "<="
    value    := STRING | NUMBER | IDENT
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .lexer import LexError, Token, tokenize


# ── AST nodes ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Compare:
    field: tuple[str, ...]
    op: str
    value: str | int | float


@dataclass(frozen=True)
class And:
    left: "Node"
    right: "Node"


@dataclass(frozen=True)
class Or:
    left: "Node"
    right: "Node"


@dataclass(frozen=True)
class Not:
    inner: "Node"


Node = Union[Compare, And, Or, Not]


class ParseError(ValueError):
    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} at position {position}")
        self.detail = message
        self.position = position


# ── Parser ────────────────────────────────────────────────────────────────────

class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.i = 0

    def peek(self) -> Token:
        return self.tokens[self.i]

    def advance(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect(self, kind: str) -> Token:
        tok = self.peek()
        if tok.kind != kind:
            raise ParseError(f"expected {kind}, got {tok.kind}", tok.position)
        return self.advance()

    # expr := or_expr
    def parse_expr(self) -> Node:
        node = self.parse_or()
        if self.peek().kind != "EOF":
            tok = self.peek()
            raise ParseError(f"unexpected {tok.kind}", tok.position)
        return node

    def parse_or(self) -> Node:
        left = self.parse_and()
        while self.peek().kind == "OR":
            self.advance()
            right = self.parse_and()
            left = Or(left, right)
        return left

    def parse_and(self) -> Node:
        left = self.parse_not()
        while self.peek().kind == "AND":
            self.advance()
            right = self.parse_not()
            left = And(left, right)
        return left

    def parse_not(self) -> Node:
        if self.peek().kind == "NOT":
            self.advance()
            return Not(self.parse_not())
        return self.parse_atom()

    def parse_atom(self) -> Node:
        tok = self.peek()
        if tok.kind == "LPAREN":
            self.advance()
            inner = self.parse_or()
            self.expect("RPAREN")
            return inner
        if tok.kind == "IDENT":
            return self.parse_compare()
        raise ParseError(f"expected field or '(' , got {tok.kind}", tok.position)

    def parse_compare(self) -> Compare:
        field = self.parse_field()
        op_tok = self.peek()
        if op_tok.kind == "COLON":
            self.advance()
            op = ":"
        elif op_tok.kind == "OP":
            self.advance()
            op = str(op_tok.value)
        else:
            raise ParseError(f"expected operator after field, got {op_tok.kind}", op_tok.position)
        value = self.parse_value()
        return Compare(field=field, op=op, value=value)

    def parse_field(self) -> tuple[str, ...]:
        parts: list[str] = []
        first = self.expect("IDENT")
        parts.append(str(first.value))
        while self.peek().kind == "DOT":
            self.advance()
            nxt = self.expect("IDENT")
            parts.append(str(nxt.value))
        return tuple(parts)

    def parse_value(self) -> str | int | float:
        tok = self.peek()
        if tok.kind == "STRING":
            self.advance()
            return str(tok.value)
        if tok.kind == "NUMBER":
            self.advance()
            assert isinstance(tok.value, (int, float))
            return tok.value
        if tok.kind == "IDENT":
            self.advance()
            return str(tok.value)
        raise ParseError(f"expected value, got {tok.kind}", tok.position)


def parse(src: str) -> Node:
    try:
        tokens = tokenize(src)
    except LexError as exc:
        raise ParseError(exc.detail, exc.position) from exc
    if len(tokens) == 1 and tokens[0].kind == "EOF":
        raise ParseError("empty query", 0)
    return _Parser(tokens).parse_expr()
```

- [ ] **Step 4: Run parser tests — expect pass**

Run: `cd backend && pytest tests/test_query_parser.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/query/parser.py backend/tests/test_query_parser.py
git commit -m "feat(query): add recursive-descent parser + AST"
```

---

## Task 3: Evaluator

**Files:**
- Create: `backend/app/query/evaluator.py`
- Modify: `backend/app/query/__init__.py`
- Create: `backend/tests/test_query_evaluator.py`

The evaluator walks the AST and applies it to a Python dict (an ECS event). Dotted-path lookup descends nested dicts; missing fields make comparisons return `False` except `!=` which returns `True`. `:` is case-insensitive substring for strings and equality for numbers; `=` is strict equality.

- [ ] **Step 1: Write the failing evaluator tests**

```python
# backend/tests/test_query_evaluator.py
"""Evaluator tests — AST + event -> bool."""

from __future__ import annotations

import pytest

from app.query import parse, evaluate


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
```

- [ ] **Step 2: Update the package init to re-export**

```python
# backend/app/query/__init__.py
"""Query DSL for ECS events — lexer, parser, evaluator."""

from .evaluator import evaluate
from .parser import And, Compare, Not, Or, ParseError, parse

__all__ = ["parse", "evaluate", "ParseError", "Compare", "And", "Or", "Not"]
```

- [ ] **Step 3: Run evaluator tests — expect failure**

Run: `cd backend && pytest tests/test_query_evaluator.py -v`
Expected: import error for `app.query.evaluator`.

- [ ] **Step 4: Implement the evaluator**

```python
# backend/app/query/evaluator.py
"""Evaluator for the query DSL.

Walks an AST against an ECS event (a nested dict) and returns a boolean.

Semantics:
  - `:` is case-insensitive substring for strings, equality for numbers.
  - `=` and `!=` are strict equality / inequality (no substring).
  - `>`, `>=`, `<`, `<=` are numeric when both sides are numeric, otherwise
    lexicographic on string coercions.
  - Missing field: all comparisons return False except `!=` which returns True.
    Rationale: NOT (x:"v") should be true for events that lack x.
"""

from __future__ import annotations

from typing import Any

from .parser import And, Compare, Node, Not, Or


_MISSING = object()


def _lookup(event: dict, path: tuple[str, ...]) -> Any:
    node: Any = event
    for part in path:
        if not isinstance(node, dict):
            return _MISSING
        if part not in node:
            return _MISSING
        node = node[part]
        if node is None:
            return _MISSING
    return node


def _compare(value: Any, op: str, target: str | int | float) -> bool:
    if value is _MISSING:
        return op == "!="

    if op == ":":
        if isinstance(target, (int, float)) and isinstance(value, (int, float)):
            return value == target
        return str(target).lower() in str(value).lower()

    if op == "=":
        if isinstance(target, (int, float)) and isinstance(value, (int, float)):
            return value == target
        return str(value) == str(target)

    if op == "!=":
        if isinstance(target, (int, float)) and isinstance(value, (int, float)):
            return value != target
        return str(value) != str(target)

    # Ordering operators
    if isinstance(target, (int, float)) and isinstance(value, (int, float)):
        lhs: Any = value
        rhs: Any = target
    else:
        lhs = str(value)
        rhs = str(target)

    if op == ">":   return lhs > rhs
    if op == ">=":  return lhs >= rhs
    if op == "<":   return lhs < rhs
    if op == "<=":  return lhs <= rhs

    raise ValueError(f"unknown operator {op!r}")


def evaluate(node: Node, event: dict) -> bool:
    if isinstance(node, Compare):
        value = _lookup(event, node.field)
        return _compare(value, node.op, node.value)
    if isinstance(node, And):
        return evaluate(node.left, event) and evaluate(node.right, event)
    if isinstance(node, Or):
        return evaluate(node.left, event) or evaluate(node.right, event)
    if isinstance(node, Not):
        return not evaluate(node.inner, event)
    raise TypeError(f"unknown AST node: {type(node).__name__}")
```

- [ ] **Step 5: Run evaluator tests — expect pass**

Run: `cd backend && pytest tests/test_query_evaluator.py -v`
Expected: all tests pass.

- [ ] **Step 6: Run full backend suite to confirm nothing else broke**

Run: `cd backend && pytest -v`
Expected: every test (lexer + parser + evaluator + existing detection/auth/rules) passes.

- [ ] **Step 7: Commit**

```bash
git add backend/app/query/__init__.py backend/app/query/evaluator.py backend/tests/test_query_evaluator.py
git commit -m "feat(query): add AST evaluator with dotted-path lookup"
```

---

## Task 4: `db.search_events`

**Files:**
- Modify: `backend/app/db.py`
- Create: `backend/tests/test_db_search.py`

Add an async function that streams events from the `events` table inside a time window, applies the predicate (the bound evaluator) in Python, and returns the matching rows decoded back into ECS dicts. Cap at `limit` matches.

- [ ] **Step 1: Write the failing search-helper test**

```python
# backend/tests/test_db_search.py
"""Tests for db.search_events — in-memory SQLite + predicate application."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

# Force an isolated in-memory DB before importing the module
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app import db                              # noqa: E402
from app.query import evaluate, parse           # noqa: E402


def _event(eid: str, source_ip: str, severity: str, ts: datetime) -> dict:
    return {
        "@timestamp": ts.isoformat().replace("+00:00", "Z"),
        "event": {"id": eid, "kind": "event", "category": "authentication",
                  "severity": severity, "outcome": "failure"},
        "source": {"ip": source_ip},
        "host": {"name": "WKS-01"},
        "message": f"event {eid}",
    }


@pytest.fixture(autouse=True)
async def _init():
    await db.init_db()


@pytest.mark.asyncio
async def test_search_events_filters_by_predicate_and_window():
    now = datetime.now(timezone.utc)
    await db.persist_event(_event("a", "10.0.0.5", "high", now - timedelta(minutes=2)))
    await db.persist_event(_event("b", "10.0.0.6", "low",  now - timedelta(minutes=2)))
    await db.persist_event(_event("c", "10.0.0.5", "high", now - timedelta(hours=2)))  # outside window

    ast = parse('source.ip:"10.0.0.5"')
    results = await db.search_events(
        predicate=lambda e: evaluate(ast, e),
        from_ts=now - timedelta(minutes=10),
        to_ts=now,
        limit=50,
    )
    ids = [r["event"]["id"] for r in results]
    assert ids == ["a"]


@pytest.mark.asyncio
async def test_search_events_honours_limit():
    now = datetime.now(timezone.utc)
    for i in range(5):
        await db.persist_event(_event(f"e{i}", "10.0.0.5", "high",
                                      now - timedelta(seconds=i)))
    ast = parse('source.ip:"10.0.0.5"')
    results = await db.search_events(
        predicate=lambda e: evaluate(ast, e),
        from_ts=now - timedelta(minutes=1),
        to_ts=now + timedelta(seconds=1),
        limit=3,
    )
    assert len(results) == 3
```

Add `pytest-asyncio` already implied by existing tests (the auth test imports `httpx` async); confirm the project uses `pytest-asyncio` in `auto` mode or add the marker explicitly. If unsure:

```bash
cd backend && pip show pytest-asyncio
```

If not installed, add `pytest-asyncio` to `backend/requirements.txt` and re-install before running.

- [ ] **Step 2: Run the search test — expect failure**

Run: `cd backend && pytest tests/test_db_search.py -v`
Expected: `AttributeError: module 'app.db' has no attribute 'search_events'`.

- [ ] **Step 3: Add `search_events` to `db.py`**

Append at the end of `backend/app/db.py`:

```python
# ── Search ────────────────────────────────────────────────────────────────────

from collections.abc import Callable           # add to existing imports if not present


async def search_events(
    predicate: Callable[[dict], bool],
    from_ts: datetime,
    to_ts: datetime,
    limit: int = 100,
) -> list[dict]:
    """Stream events in [from_ts, to_ts), apply predicate in Python, return up to `limit`.

    Rows are scanned newest-first so the most recent matches are returned when
    the window is wider than `limit` matches.
    """
    matches: list[dict] = []
    async with get_session() as s:
        stmt = (
            select(StoredEvent.raw_json)
            .where(StoredEvent.timestamp >= from_ts)
            .where(StoredEvent.timestamp < to_ts)
            .order_by(StoredEvent.timestamp.desc())
        )
        result = await s.execute(stmt)
        for (raw,) in result.all():
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if predicate(event):
                matches.append(event)
                if len(matches) >= limit:
                    break
    return list(reversed(matches))   # caller wants oldest-first
```

(Move the `from collections.abc import Callable` up next to the other top-of-file imports if not already there. Verify the file still parses.)

- [ ] **Step 4: Run the search test — expect pass**

Run: `cd backend && pytest tests/test_db_search.py -v`
Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/tests/test_db_search.py
git commit -m "feat(db): add search_events with time-window + predicate"
```

---

## Task 5: Wire `/api/search` to the DSL; move ES passthrough

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_search_api.py`

Replace the body of `GET /api/search` to: parse `q`, default `from`/`to`, run the predicate via `db.search_events`, return JSON. Move the previous ES-passthrough body to `GET /api/search/es`.

- [ ] **Step 1: Write the failing API test**

```python
# backend/tests/test_search_api.py
"""Integration tests for /api/search backed by the DSL + SQLite."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from httpx import ASGITransport, AsyncClient                       # noqa: E402

from app import db                                                  # noqa: E402
from app.main import app                                            # noqa: E402


def _event(eid: str, source_ip: str, severity: str, ts: datetime) -> dict:
    return {
        "@timestamp": ts.isoformat().replace("+00:00", "Z"),
        "event": {"id": eid, "kind": "event", "category": "authentication",
                  "severity": severity, "outcome": "failure"},
        "source": {"ip": source_ip},
        "host": {"name": "WKS-01"},
        "message": "test",
    }


@pytest.fixture(autouse=True)
async def _seed():
    await db.init_db()
    now = datetime.now(timezone.utc)
    await db.persist_event(_event("a", "10.0.0.5", "high", now - timedelta(minutes=1)))
    await db.persist_event(_event("b", "10.0.0.6", "low",  now - timedelta(minutes=1)))


@pytest.mark.asyncio
async def test_search_matches_by_ip():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get('/api/search', params={"q": 'source.ip:"10.0.0.5"'})
    assert r.status_code == 200
    body = r.json()
    ids = [e["event"]["id"] for e in body["results"]]
    assert ids == ["a"]
    assert body["source"] == "sqlite"
    assert body["matched"] == 1


@pytest.mark.asyncio
async def test_parse_error_returns_400_with_position():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get('/api/search', params={"q": 'source.ip:'})
    assert r.status_code == 400
    body = r.json()
    assert "detail" in body
    assert "position" in body


@pytest.mark.asyncio
async def test_default_window_is_15_minutes():
    now = datetime.now(timezone.utc)
    # Insert an old event that should NOT appear under the default window
    await db.persist_event(_event("old", "10.0.0.5", "high", now - timedelta(hours=2)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get('/api/search', params={"q": 'source.ip:"10.0.0.5"'})
    ids = [e["event"]["id"] for e in r.json()["results"]]
    assert "old" not in ids
    assert "a" in ids


@pytest.mark.asyncio
async def test_limit_param_honoured():
    now = datetime.now(timezone.utc)
    for i in range(10):
        await db.persist_event(_event(f"x{i}", "10.0.0.7", "high",
                                      now - timedelta(seconds=i)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get('/api/search', params={"q": 'source.ip:"10.0.0.7"', "limit": 3})
    assert len(r.json()["results"]) == 3
```

- [ ] **Step 2: Run the API test — expect failure**

Run: `cd backend && pytest tests/test_search_api.py -v`
Expected: tests fail (the existing `/api/search` runs ES passthrough; returns 200 but with `source: "unavailable"`, no `matched` field, etc.).

- [ ] **Step 3: Modify `main.py` — replace `/api/search` and add `/api/search/es`**

In `backend/app/main.py`, locate the existing block:

```python
# ── ElasticSearch passthrough search ──────────────────────────────────────────

@app.get("/api/search", tags=["Telemetry"])
async def search(q: str = Query(..., min_length=1)):
    results = await elastic.search(q)
    return {
        "results": results,
        "source": "elasticsearch" if elastic.is_available() else "unavailable",
    }
```

Replace it with:

```python
# ── Search (DSL over SQLite ring) + ES passthrough ────────────────────────────

from datetime import datetime, timedelta, timezone   # add near the top of the file if not present
from fastapi import Request                           # already imported via other fastapi imports

from .query import ParseError, evaluate, parse


def _parse_window(from_q: str | None, to_q: str | None) -> tuple[datetime, datetime]:
    to_ts = datetime.fromisoformat(to_q.replace("Z", "+00:00")) if to_q else datetime.now(timezone.utc)
    from_ts = (
        datetime.fromisoformat(from_q.replace("Z", "+00:00")) if from_q
        else to_ts - timedelta(minutes=15)
    )
    return from_ts, to_ts


@app.get("/api/search", tags=["Telemetry"])
async def search(
    q: str = Query(..., min_length=1),
    from_: str | None = Query(None, alias="from"),
    to:    str | None = Query(None),
    limit: int = Query(100, le=500),
):
    """DSL search over persisted events. Time window defaults to last 15 minutes."""
    try:
        ast = parse(q)
    except ParseError as exc:
        raise HTTPException(
            status_code=400,
            detail={"detail": exc.detail, "position": exc.position},
        ) from exc

    from_ts, to_ts = _parse_window(from_, to)
    results = await db.search_events(
        predicate=lambda e: evaluate(ast, e),
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
    )
    return {
        "results": results,
        "matched": len(results),
        "from": from_ts.isoformat(),
        "to": to_ts.isoformat(),
        "source": "sqlite",
    }


@app.get("/api/search/es", tags=["Telemetry"])
async def search_es(q: str = Query(..., min_length=1)):
    """Raw ElasticSearch passthrough — only useful when --profile elastic is up."""
    results = await elastic.search(q)
    return {
        "results": results,
        "source": "elasticsearch" if elastic.is_available() else "unavailable",
    }
```

Add `from datetime import datetime, timedelta, timezone` near the top of the file if not already imported. (Check: there's no `datetime` import currently, so add the line under `from contextlib import asynccontextmanager`.)

- [ ] **Step 4: Adjust the test for FastAPI's 400 body shape**

FastAPI wraps `HTTPException(detail=...)` as `{"detail": <whatever>}`. The test asserts `"detail" in body` and `"position" in body` — that will fail because position is nested. Update the test:

```python
# in test_search_api.py — replace test_parse_error_returns_400_with_position with:

@pytest.mark.asyncio
async def test_parse_error_returns_400_with_position():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get('/api/search', params={"q": 'source.ip:'})
    assert r.status_code == 400
    body = r.json()
    assert "detail" in body                 # FastAPI wrapper
    inner = body["detail"]
    assert "detail" in inner and "position" in inner
```

- [ ] **Step 5: Run the API test — expect pass**

Run: `cd backend && pytest tests/test_search_api.py -v`
Expected: all four tests pass.

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend && pytest -v`
Expected: all tests pass (lexer, parser, evaluator, db.search, search API, plus existing detection/auth/rules).

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/tests/test_search_api.py
git commit -m "feat(api): wire /api/search to DSL; move ES passthrough to /api/search/es"
```

---

## Task 6: Frontend — time-range helper

**Files:**
- Create: `frontend/src/lib/timeRange.ts`

A tiny module mapping preset labels to `{from, to}` ISO strings, plus a parser for custom inputs.

- [ ] **Step 1: Create the file**

```typescript
// frontend/src/lib/timeRange.ts
export type Preset = '5m' | '15m' | '1h' | '24h' | 'custom'

const PRESET_MINUTES: Record<Exclude<Preset, 'custom'>, number> = {
  '5m': 5,
  '15m': 15,
  '1h': 60,
  '24h': 60 * 24,
}

export interface TimeRange {
  from: string   // ISO 8601 UTC
  to: string     // ISO 8601 UTC
}

export function rangeFromPreset(preset: Exclude<Preset, 'custom'>, now = new Date()): TimeRange {
  const minutes = PRESET_MINUTES[preset]
  const to = now
  const from = new Date(to.getTime() - minutes * 60_000)
  return { from: from.toISOString(), to: to.toISOString() }
}

export function isValidIso(s: string): boolean {
  const d = new Date(s)
  return !isNaN(d.getTime())
}
```

No tests for this slice — it's a thin pure helper; the component tests will exercise it transitively if added later.

- [ ] **Step 2: Build the frontend to confirm it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/timeRange.ts
git commit -m "feat(ui): add timeRange helper for search drawer"
```

---

## Task 7: Frontend — `SearchPanel` component

**Files:**
- Create: `frontend/src/components/SearchPanel.tsx`

A right-side slide-in drawer with: query input, preset selector, results list, JSON detail on row click, copy-link button. The drawer is uncontrolled internally but accepts `query`, `preset`, and `open` from props, so the parent can drive it from a pivot click.

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/SearchPanel.tsx
import { useEffect, useState } from 'react'
import type { EcsEvent } from '../types'
import { ecs } from '../types'
import { rangeFromPreset, type Preset } from '../lib/timeRange'

interface Props {
  open: boolean
  initialQuery: string
  initialPreset: Preset
  onClose: () => void
}

interface SearchResponse {
  results: EcsEvent[]
  matched: number
  from: string
  to: string
  source: string
}

interface ApiError {
  detail: { detail: string; position: number }
}

export function SearchPanel({ open, initialQuery, initialPreset, onClose }: Props) {
  const [query, setQuery] = useState(initialQuery)
  const [preset, setPreset] = useState<Preset>(initialPreset)
  const [results, setResults] = useState<EcsEvent[]>([])
  const [matched, setMatched] = useState(0)
  const [error, setError] = useState<{ message: string; position: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => { setQuery(initialQuery) }, [initialQuery])
  useEffect(() => { setPreset(initialPreset) }, [initialPreset])

  async function run() {
    if (!query.trim() || preset === 'custom') return
    setLoading(true); setError(null)
    const { from, to } = rangeFromPreset(preset)
    const url = `/api/search?q=${encodeURIComponent(query)}&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&limit=200`
    try {
      const r = await fetch(url)
      if (r.status === 400) {
        const body = await r.json() as ApiError
        setError({ message: body.detail.detail, position: body.detail.position })
        setResults([]); setMatched(0)
      } else {
        const body = await r.json() as SearchResponse
        setResults(body.results); setMatched(body.matched)
      }
    } catch (e) {
      setError({ message: String(e), position: 0 })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (open) run() /* eslint-disable-next-line */ }, [open, initialQuery, initialPreset])

  function copyLink() {
    const u = new URL(window.location.href)
    u.searchParams.set('q', query)
    u.searchParams.set('preset', preset)
    void navigator.clipboard.writeText(u.toString())
  }

  if (!open) return null

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[480px] bg-slate-950 border-l border-slate-800 shadow-2xl z-40 flex flex-col">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
          <h2 className="text-sm font-semibold text-slate-200">Investigation Search</h2>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-200 text-lg leading-none">×</button>
      </div>

      <div className="px-4 py-3 space-y-2 border-b border-slate-800">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') run() }}
          placeholder='source.ip:"10.0.0.5" AND event.severity:high'
          className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
        />
        <div className="flex items-center gap-2 text-xs">
          {(['5m', '15m', '1h', '24h'] as const).map(p => (
            <button
              key={p}
              onClick={() => setPreset(p)}
              className={`px-2 py-0.5 rounded border ${preset === p
                ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30'
                : 'bg-slate-900 text-slate-500 border-slate-700 hover:text-slate-300'}`}
            >{p}</button>
          ))}
          <button onClick={run} className="ml-auto px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/30">
            {loading ? '…' : 'Run'}
          </button>
          <button onClick={copyLink} className="px-2 py-0.5 rounded text-slate-500 hover:text-slate-300">copy link</button>
        </div>
        {error && (
          <div className="text-xs text-red-400 font-mono">
            {error.message} <span className="text-slate-500">(col {error.position})</span>
          </div>
        )}
        {!error && <div className="text-[10px] text-slate-500">{matched} matched</div>}
      </div>

      <ul className="flex-1 overflow-y-auto divide-y divide-slate-800/60">
        {results.map(e => {
          const expanded = expandedId === e.event.id
          return (
            <li key={e.event.id} className="px-4 py-2 hover:bg-slate-800/40">
              <button
                onClick={() => setExpandedId(expanded ? null : e.event.id)}
                className="w-full text-left"
              >
                <div className="flex items-center justify-between text-[10px] text-slate-500 tabular-nums">
                  <span>{new Date(e['@timestamp']).toLocaleTimeString('en-GB', { hour12: false })}</span>
                  <span className="text-slate-600">{ecs.severity(e)}</span>
                </div>
                <div className="text-xs text-slate-300 truncate">{e.message}</div>
                <div className="text-[10px] text-slate-600">{ecs.source(e)}{ecs.dest(e) ? ` → ${ecs.dest(e)}` : ''}</div>
              </button>
              {expanded && (
                <pre className="mt-1 text-[10px] text-slate-400 bg-slate-900 rounded p-2 overflow-x-auto">
                  {JSON.stringify(e, null, 2)}
                </pre>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors. (If `ecs.source`/`ecs.dest` signatures don't exist, check `frontend/src/types/index.ts` and adjust accordingly — they're used in `AlertFeed.tsx` so they exist.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SearchPanel.tsx
git commit -m "feat(ui): add SearchPanel drawer for investigation queries"
```

---

## Task 8: Pivot button on alerts + wire to `App`

**Files:**
- Modify: `frontend/src/components/AlertFeed.tsx`
- Modify: `frontend/src/App.tsx`

Add an `onPivot?: (q: string) => void` prop to `AlertFeed`. Each alert row gets a small `🔍` button (visible only when `event.source?.ip` is present) that, when clicked, calls `onPivot` with `source.ip:"<ip>"`. In `App.tsx`, hold `pivotState = { open, query, preset }` and pass a setter to `AlertFeed`. Mount `<SearchPanel />`.

- [ ] **Step 1: Update `AlertFeed.tsx`**

Replace the file with:

```tsx
// frontend/src/components/AlertFeed.tsx
import type { EcsEvent } from '../types'
import { ecs } from '../types'

interface Props {
  events: EcsEvent[]
  onPivot?: (query: string) => void
}

const SEV_BADGE: Record<string, string> = {
  low:      'bg-green-500/20 text-green-400 border-green-500/30',
  medium:   'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  high:     'bg-orange-500/20 text-orange-400 border-orange-500/30',
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-GB', { hour12: false })
}

export function AlertFeed({ events, onPivot }: Props) {
  if (events.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600 text-sm">
        Awaiting events…
      </div>
    )
  }

  return (
    <ul className="overflow-y-auto h-full divide-y divide-slate-800/60">
      {[...events].reverse().map(e => {
        const sev = ecs.severity(e)
        const ip = e.source?.ip
        return (
          <li key={e.event.id} className="px-4 py-2.5 hover:bg-slate-800/40 transition-colors">
            <div className="flex items-center justify-between gap-2 mb-1">
              <div className="flex items-center gap-1.5">
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${SEV_BADGE[sev]}`}>
                  {sev.toUpperCase()}
                </span>
                {ecs.isAlert(e) && (
                  <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                    ALERT
                  </span>
                )}
                {ecs.technique(e) && (
                  <span className="text-[9px] font-mono text-purple-400">{ecs.technique(e)}</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {onPivot && ip && (
                  <button
                    onClick={() => onPivot(`source.ip:"${ip}"`)}
                    title={`Pivot to events from ${ip}`}
                    className="text-[10px] text-cyan-400 hover:text-cyan-300"
                  >🔍</button>
                )}
                <span className="text-[10px] text-slate-500 tabular-nums">{fmtTime(e['@timestamp'])}</span>
              </div>
            </div>
            <div className="text-xs font-semibold text-slate-300 truncate">
              {e.rule?.name ?? ecs.type(e)}
            </div>
            <div className="text-[11px] text-slate-500 truncate">{e.message}</div>
            <div className="text-[10px] text-slate-600 mt-0.5">
              {ecs.source(e)}{ecs.dest(e) ? ` → ${ecs.dest(e)}` : ''}
            </div>
          </li>
        )
      })}
    </ul>
  )
}
```

- [ ] **Step 2: Update `App.tsx` — add pivot state + mount `SearchPanel`**

In `frontend/src/App.tsx`:

1. Add the import near the other component imports:
   ```tsx
   import { SearchPanel } from './components/SearchPanel'
   import type { Preset } from './lib/timeRange'
   ```

2. Inside `App()`, alongside the other `useState` calls, add:
   ```tsx
   const [pivot, setPivot] = useState<{ open: boolean; query: string; preset: Preset }>({
     open: false, query: '', preset: '15m',
   })

   // Read deep-link params on mount
   useEffect(() => {
     const params = new URLSearchParams(window.location.search)
     const q = params.get('q')
     const p = (params.get('preset') ?? '15m') as Preset
     if (q) setPivot({ open: true, query: q, preset: p })
   }, [])
   ```

3. Find the existing alert-feed mount near the bottom:
   ```tsx
   <AlertFeed events={[...events, ...alerts].slice(-60)} />
   ```
   Replace with:
   ```tsx
   <AlertFeed
     events={[...events, ...alerts].slice(-60)}
     onPivot={(query) => setPivot({ open: true, query, preset: '15m' })}
   />
   ```

4. Just before the closing `</main>` (or after it, but inside the root div), mount the drawer:
   ```tsx
   <SearchPanel
     open={pivot.open}
     initialQuery={pivot.query}
     initialPreset={pivot.preset}
     onClose={() => setPivot(s => ({ ...s, open: false }))}
   />
   ```

- [ ] **Step 3: Type-check + dev build**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Manual smoke test**

Run, in two terminals:

```bash
cd backend && uvicorn app.main:app --reload
```

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173`. Verify:
1. The dashboard loads as before.
2. Wait for a few alerts/events with a `source.ip` to appear in the bottom Live Alert Feed.
3. Click 🔍 on one of them — drawer opens with `source.ip:"…"` pre-filled.
4. Try `source.ip:"10.0"` (substring match should return events). Try a bad query `source.ip:` — red error message with column position appears.
5. Switch preset 5m/15m/1h — list refreshes.
6. Click "copy link", paste into a new tab — drawer opens with same query.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AlertFeed.tsx frontend/src/App.tsx
git commit -m "feat(ui): pivot button + SearchPanel wired into dashboard"
```

---

## Task 9: README + ARCHITECTURE doc updates

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`

Document the new endpoint, the DSL, three example queries, and the small breaking change.

- [ ] **Step 1: Add a "Querying events" section to `README.md`**

Insert after the existing "API surface" section. Use the README's existing tone (terse, table-heavy where useful).

```markdown
---

## Querying events — the DSL

Click the 🔍 button on any alert in the feed to open the investigation drawer
pre-filled with `source.ip:"…"`. The same query language drives `/api/search`:

```
GET /api/search?q=<dsl>&from=<iso>&to=<iso>&limit=N
```

Time defaults to the last 15 minutes.

| Example | Meaning |
|---|---|
| `source.ip:"10.0.0.5"` | substring match on the source IP |
| `event.severity:high AND event.category:authentication` | two clauses |
| `source.ip:"10.0.0.5" AND NOT event.outcome:success` | exclude successes |
| `risk_score >= 50` | numeric comparison |

Grammar lives in [`backend/app/query/parser.py`](backend/app/query/parser.py).
Operator semantics: `:` is case-insensitive substring (or numeric equality),
`=`/`!=` are strict, and `>` `>=` `<` `<=` are numeric where both sides parse
as numbers.

> **Breaking change:** the previous ElasticSearch passthrough that lived at
> `GET /api/search` moved to `GET /api/search/es`. The new `/api/search` is
> DSL-driven and queries the SQLite ring buffer.
```

- [ ] **Step 2: Update the pipeline diagram in `docs/ARCHITECTURE.md`**

Add a new "Investigation" box / paragraph describing the query package and how `/api/search` flows through `parse → evaluate → db.search_events`. Match the existing prose style. Look at the file first to find the right insertion point:

```bash
cd .. && head -80 docs/ARCHITECTURE.md
```

Insert a 4-6 line paragraph after the existing pipeline description, e.g.:

```markdown
### Investigation (added 2026-05-17)

`GET /api/search` parses a small query DSL (`backend/app/query/`) and runs the
resulting AST as a Python predicate against events in SQLite, scoped to a time
window. The AST is the storage-agnostic indirection layer: if events later move
to ES or DuckDB, only the evaluator changes. The previous ES passthrough is
preserved at `GET /api/search/es`.
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/ARCHITECTURE.md
git commit -m "docs: document the query DSL and /api/search breaking change"
```

---

## Final verification

- [ ] **Run the full backend test suite**

Run: `cd backend && pytest -v`
Expected: every test passes (including the four new test files).

- [ ] **Run linter**

Run: `cd backend && ruff check app tests`
Expected: no errors.

- [ ] **Type-check frontend**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Manual smoke test (repeat Task 8 Step 4)**

Open the dashboard, click 🔍 on an alert, try at least one valid and one invalid query, switch presets, copy a link.

- [ ] **Confirm the spec is satisfied**

Re-read [`docs/superpowers/specs/2026-05-17-investigation-pivot-and-query-dsl-design.md`](../specs/2026-05-17-investigation-pivot-and-query-dsl-design.md) one more time — every "Files" entry and every "Tests" coverage bullet should be checked off above.
