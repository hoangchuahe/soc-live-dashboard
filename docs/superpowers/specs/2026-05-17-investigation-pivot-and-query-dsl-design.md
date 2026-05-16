# Investigation Pivot + Query DSL — Design

**Date:** 2026-05-17
**Status:** Draft for implementation
**Scope:** One slice. Real-stream ingestion is a likely *next* slice and is explicitly out of scope here.

## Why this, why now

The dashboard currently shows events and alerts streaming past, but offers no way to ask *"what else did this entity do?"* — the single most common SOC-analyst question. Adding a small query language and an alert-pivot workflow unlocks investigation, and produces a reusable AST that later slices (rule-authoring previews, replay filters, ingestion-side filters) can build on.

Learning value drove the choice:
- Hand-rolled lexer + recursive-descent parser is the most transferable skill on the table.
- The AST is the right indirection point if storage later moves to ES or DuckDB.
- The result is immediately visible and usable in the UI.

## DSL — v1 grammar

Intentionally small. Easy to extend, no library dependency.

```
expr     = or_expr
or_expr  = and_expr ("OR" and_expr)*
and_expr = not_expr ("AND" not_expr)*
not_expr = "NOT"? atom
atom     = comparison | "(" expr ")"
compare  = field op value
field    = IDENT ("." IDENT)*          # ECS dotted paths, e.g. source.ip
op       = ":" | "=" | "!=" | ">" | ">=" | "<" | "<="
value    = STRING | NUMBER | IDENT
```

Operator semantics:

| op   | string lhs                          | numeric lhs |
|------|-------------------------------------|-------------|
| `:`  | case-insensitive substring          | equality    |
| `=`  | exact equality                      | equality    |
| `!=` | inverse of `=`                      | inverse     |
| `>` `>=` `<` `<=` | lexicographic           | numeric     |

`IDENT` matches `[A-Za-z_][A-Za-z0-9_]*` and is also accepted as a value (treated as a bare string), so `event.severity:high` works without quoting.

`STRING` is double-quoted with `\"` escape.

`NUMBER` is integer or float.

### Examples
```
source.ip:"10.0.0.5"
event.severity:high AND event.category:authentication
source.ip:"10.0.0.5" AND NOT event.outcome:success
risk_score >= 50 OR event.severity:critical
(source.ip:"10.0.0.5" OR source.ip:"10.0.0.6") AND event.outcome:failure
```

### Time range — outside the DSL
Time is a structural parameter (`from`, `to`), not part of the language. Every SIEM I've used regrets putting time inside the syntax (Splunk's `earliest=`/`latest=` are awkward; Lucene's range queries on timestamps are verbose). Keep it out.

## AST node shapes (Python)

```python
@dataclass
class And: left: Node; right: Node
@dataclass
class Or:  left: Node; right: Node
@dataclass
class Not: inner: Node
@dataclass
class Compare:
    field: tuple[str, ...]   # ("source", "ip")
    op: str                  # ":", "=", "!=", ">", ">=", "<", "<="
    value: str | int | float
Node = And | Or | Not | Compare
```

## API

```
GET /api/search?q=<dsl>&from=<iso8601>&to=<iso8601>&limit=N
```

- `q` required. Empty / whitespace-only → 400.
- `from`, `to` optional ISO-8601. Default `to=now`, `from=now - 15 min`.
- `limit` default 100, max 500.
- Returns `{ "results": [...], "matched": N, "source": "sqlite" }`.
- Parse errors return **400** with `{"detail": "...", "position": <col>}`.

Existing `/api/search?q=...` (ES passthrough) moves to **`GET /api/search/es?q=...`**. Note this in the README under a small "Migration" callout.

## Backend changes

### New package: `backend/app/query/`
- `lexer.py` — `tokenize(src: str) -> list[Token]`; emits tokens with positions for error reporting.
- `parser.py` — `parse(src: str) -> Node`; recursive-descent; raises `ParseError(message, position)`.
- `evaluator.py` — `evaluate(ast: Node, event: dict) -> bool`; dotted-path lookup against the ECS document; missing field → comparison is `False` (except `!=` which is `True`).
- `__init__.py` — re-exports `parse`, `evaluate`, `ParseError`.

### Storage: `backend/app/db.py`
- Add `async search_events(predicate, from_ts, to_ts, limit) -> list[dict]`:
  - Streams rows from SQLite filtered by `timestamp BETWEEN ?` and `kind` if needed.
  - Applies the Python predicate (the evaluator bound with the AST).
  - Stops once `limit` matches found.
- Indexes: confirm an index on `(timestamp)` exists; add if not.

### Route wiring: `backend/app/main.py`
- Replace `/api/search` body to:
  1. `parse(q)` (catch `ParseError` → 400)
  2. Parse `from`/`to` to UTC datetimes (defaults as above)
  3. `await db.search_events(lambda e: evaluate(ast, e), from_ts, to_ts, limit)`
- Move existing ES-passthrough body to `/api/search/es`.

## Frontend changes

### New: `frontend/src/components/SearchPanel.tsx`
A right-side drawer (slides in over the layout):
- Text input bound to `q`.
- Time-range select: `5m`, `15m` (default), `1h`, `24h`, plus "custom" (two datetime inputs).
- Results: time-sorted list of event rows (timestamp, category, severity, source.ip → host.name). Click row → expanded JSON.
- Error region: shows `ParseError.detail` with a caret under `position`.
- "Copy as URL" copies a deep link `?q=...&from=...&to=...`.

### New: `frontend/src/lib/timeRange.ts`
- Helpers to convert preset → `{from, to}` ISO strings.

### Edited: `frontend/src/components/AlertFeed.tsx`
- Each alert row: small `🔍 Pivot` button → calls a prop callback with `{ field: "source.ip", value: alert.source?.ip, window: "15m" }`.
- Falls back gracefully if the alert has no `source.ip` (button disabled).

### Edited: `frontend/src/App.tsx`
- Mount `<SearchPanel />`, hold `searchState` in `App`, pass setter to `AlertFeed`.
- Read initial state from URL search params on mount so deep links work.

### Out of scope (no TS parser in v1)
Server is authoritative; invalid queries surface as inline 400s. Adding a TS port is a clean follow-up.

## Tests

### `backend/tests/test_query.py` (new) — table-driven
- **Lexer:** `("source.ip:\"x\"", [IDENT, DOT, IDENT, COLON, STRING])` etc.
- **Parser happy path:** for each example query in this spec, assert the AST shape.
- **Parser errors:** unclosed string, dangling `AND`, mismatched paren, empty input → assert `ParseError` with position.
- **Evaluator:** parametrize `(event, query, expected)`:
  - substring `:` matches on string
  - exact `=` matches and mismatches
  - numeric `>=` against `risk_score`
  - `NOT` negation
  - `AND` / `OR` precedence (`a OR b AND c` parses as `a OR (b AND c)`)
  - missing field → `False` for `=`, `True` for `!=`

### `backend/tests/test_search_api.py` (new)
- Seed SQLite with ~10 fixture events (mix of severities, source IPs).
- Hit `/api/search?q=source.ip:"10.0.0.5"&from=...&to=...` → assert returned ids.
- Parse error → 400 with `detail` and `position` fields.
- Verify `limit` is honored.

### Coverage target
At least one assertion per AST node type, per operator, and one parse-error per error class.

## Trade-offs (write these down so future-me doesn't relitigate)

| Decision | Alternative considered | Why this one |
|---|---|---|
| Hand-rolled parser | `lark`, `pyparsing`, Lucene | Learning. ~150 LOC, no deps. |
| Python predicate over SQLite | Translate AST → SQL `WHERE` | Volume is small; ECS dotted paths fight SQL columns; AST stays storage-agnostic. |
| Time outside DSL | `earliest=`/`latest=` inside | Cleaner grammar; structural params are easier for UI to manipulate. |
| Substring on `:` for strings | Exact on `:` (Lucene-ish) | Investigation flow wants forgiving match; `=` covers exact. |
| Server-only validation in v1 | TS port of parser | Cheaper; round-trip is fast enough; can add later without breaking API. |
| ES passthrough stays separate | Route DSL through ES | Two backends doubles tests; ES is optional infra; revisit if/when ES becomes the canonical store. |

## Phases (for the plan)

1. Lexer + tests
2. Parser + AST + tests (errors with positions)
3. Evaluator + tests
4. `db.search_events` + a small integration test
5. Wire `/api/search` to DSL; move ES passthrough to `/api/search/es`; update OpenAPI
6. `SearchPanel` + time-range picker; mount in `App`
7. Pivot button on `AlertFeed`; wire to `SearchPanel`
8. URL deep-linking (read query params on mount)
9. README section: "Querying events" with three example queries
10. Update `docs/ARCHITECTURE.md` — add the `query/` box to the pipeline diagram

## Non-goals (v1)

- Aggregations (`| count by source.ip`) — v2; needs GROUP-BY semantics
- Wildcards / regex / fuzzy
- Saved searches, query history
- Field autocomplete in the UI (dropdown of known ECS fields is fine; full schema-aware autocomplete is v2)
- ES-backed DSL execution
- Real-stream ingestion (syslog / JSON-over-TCP) — that's the next slice

## Open follow-ups (intentionally deferred)

- `risk_score` is currently per-entity, not per-event. Either denormalize onto the event at emit time, or have the evaluator special-case it via a function call. Pick at implementation time.
- Time-zone handling: store and compare in UTC; surface user's local TZ only in the UI.
