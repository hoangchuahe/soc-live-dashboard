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
            tokens.append(Token("LPAREN", "(", i))
            i += 1
            continue
        if ch == ")":
            tokens.append(Token("RPAREN", ")", i))
            i += 1
            continue
        if ch == ":":
            tokens.append(Token("COLON", ":", i))
            i += 1
            continue
        if ch == ".":
            tokens.append(Token("DOT", ".", i))
            i += 1
            continue

        # Operators — try two-char first
        two = src[i : i + 2]
        if two in _TWO_CHAR_OPS:
            tokens.append(Token("OP", two, i))
            i += 2
            continue
        if ch in _ONE_CHAR_OPS:
            tokens.append(Token("OP", ch, i))
            i += 1
            continue

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
            try:
                value: float | int = float(text) if "." in text else int(text)
            except ValueError as exc:
                raise LexError(f"invalid numeric literal {text!r}", start) from exc
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
