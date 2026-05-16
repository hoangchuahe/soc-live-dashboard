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

    if op == ">":
        return lhs > rhs
    if op == ">=":
        return lhs >= rhs
    if op == "<":
        return lhs < rhs
    if op == "<=":
        return lhs <= rhs

    raise ValueError(f"unknown operator {op!r}")


def evaluate(node: Node, event: dict) -> bool:
    """Evaluate an AST node against an ECS event dict."""
    if isinstance(node, Compare):
        value = _lookup(event, node.field)
        return _compare(value, node.op, node.value)
    if isinstance(node, And):
        return evaluate(node.left, event) and evaluate(node.right, event)
    if isinstance(node, Or):
        return evaluate(node.left, event) or evaluate(node.right, event)
    if isinstance(node, Not):
        return not evaluate(node.inner, event)
    raise TypeError(f"unknown AST node type {type(node)!r}")
