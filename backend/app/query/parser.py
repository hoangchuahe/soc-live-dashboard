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

from .lexer import LexError, Token, tokenize

# ── AST nodes ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Compare:
    field: tuple[str, ...]
    op: str
    value: str | int | float


@dataclass(frozen=True)
class And:
    left: Node
    right: Node


@dataclass(frozen=True)
class Or:
    left: Node
    right: Node


@dataclass(frozen=True)
class Not:
    inner: Node


Node = Compare | And | Or | Not


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
        raise ParseError(f"expected field or '(', got {tok.kind}", tok.position)

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
            if not isinstance(tok.value, (int, float)):
                raise ParseError(f"invalid numeric token value {tok.value!r}", tok.position)
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
