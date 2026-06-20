# Architecture

## Pipeline

```
┌─────────────┐
│  Simulator  │   (random-walk metrics, weighted geo, MITRE-tagged events)
└──────┬──────┘
       │  ECS event
       ▼
┌─────────────────────────┐
│   Detection Engine      │   sliding-window state (collections.deque)
│  ┌──────────────────┐   │   per (rule_id, entity)
│  │ Sigma YAML rules │   │
│  │  detections/*.yml│   │   selection match → threshold check → fire
│  └──────────────────┘   │
└──────┬──────────────────┘
       │
       ├──► Detection (event.kind=alert) ──► RiskTracker.bump(entity, weight)
       │         └──► CorrelationEngine.ingest(event, dets) ──► CorrelatedDetection
       │                                            │
       │                                            ▼
       │                                   exponential-decay risk score
       │
       ├──► Ring buffer (deque, maxlen=500)  → /api/events?since=<id>
       │
       ├──► Prometheus counters             → /metrics
       │
       └──► Best-effort ES indexing         → soc-events index

   ▼
WebSocket /ws    {tick, metrics, event, alerts[]}
   │
   ▼
React + D3 dashboard (rolling buffers per panel)
```

## Why this shape

### Detection engine in a single process

Modeled after Splunk's correlation searches and Elastic's threshold rules. State
is held in `collections.deque` keyed by `(rule_id, entity)` — O(1) add, O(N) prune
on each evaluation, which is fine for thousands of rules at single-host throughput.

For horizontal scale the state moves into Redis (using sorted sets with TTL) or a
dedicated stream processor (Apache Flink, Bytewax). The interface
(`engine.evaluate(event) -> list[Detection]`) is unchanged.

### Risk-Based Alerting (RBA)

Splunk's RBA is the modern alternative to alert-per-rule fatigue. Low-fidelity
signals contribute risk weight to the offending entity (host / user / IP); the
*entity* crosses an alert threshold, not the rule. The dashboard implements the
core mechanic — `RiskTracker.bump(entity, weight)` — and decays scores
exponentially with a 30-minute half-life so transient noise fades.

### Correlation (multi-stage detection)

Base rules are single-event/threshold. A `CorrelationEngine` sits above them and
recognises an ordered sequence of base-rule fires for one entity within a window
(`temporal_ordered`, mirroring Sigma correlation + Splunk RBA). It consumes the
base `Detection`s plus the triggering event — re-resolving the `group-by` field
from the event so stages keyed differently by their base rules still correlate on
a common field (`host.name`). On completion it emits one higher-severity
`CorrelatedDetection` referencing its child stages. State is in-process per
`(correlation_rule, entity)`; it would move to Redis/Flink for horizontal scale,
exactly like the base engine.

### ECS schema everywhere

Every event flows in ECS shape (`@timestamp`, `event.*`, `source.*`, `host.*`,
`threat.*`). This means:

- The **same event** indexable into Elastic Security with zero remap
- Translation to OCSF or Splunk CIM is a column-rename (see `docs/SCHEMA.md`)
- D3 components consume the event via small `ecs.*` accessor helpers

### Ring buffer + replay

The last 500 events live in an in-memory `deque`. The `/api/events?since=<id>`
endpoint backfills clients reconnecting after a network blip — no need to query
ES on the hot path. This is the same pattern Kafka uses for partition replay,
implemented at proof-of-concept scale.

### Best-effort ES indexing

Each event is fired to ElasticSearch via `asyncio.create_task` so the WebSocket
tick is never blocked by indexing latency. If ES is down the dashboard runs
fine; the optional `--profile elastic` brings up ES + Kibana for the demo.

### Investigation search (DSL)

`GET /api/search` parses a small query DSL — lexer → recursive-descent parser →
AST evaluator, all in [`backend/app/query/`](../backend/app/query) — and runs the
resulting predicate against events in SQLite, scoped to a time window. The AST
is the storage-agnostic indirection layer: if events later move to a different
store, only the evaluator changes. The previous ES passthrough is preserved at
`GET /api/search/es`. The frontend exposes the same DSL through a dedicated
**Discover** view (search bar + D3 event histogram + results table); a pivot
button on each alert deep-links into Discover pre-filled with `source.ip:"…"`.

## What's deliberately *not* in this build

| Pattern                 | Why omitted (and how to add it)                                                                           |
|-------------------------|-----------------------------------------------------------------------------------------------------------|
| Redis pub/sub fan-out   | Single-instance for the demo. Add `aioredis.publish()` after every ES index call; subscribe in WS handler |
| Kafka / NATS ingestion  | Out of scope for in-memory simulator. Real deployment: Beats → Kafka → consumer pool → engine            |
| Detection-rule CI       | Rule schema is ready (`yaml`); add a `pytest` job per rule with sample event → expected detection         |
| Alert lifecycle         | `acknowledged / in_progress / closed` states + assignee; `PATCH /api/alerts/{id}` and a workflow column   |
| Dead-letter queue       | Catch parse errors at ingestion and surface to a `dlq` panel — operational maturity signal                |
| Hot/warm/cold tiering   | ES ILM policies for retention; cold tier to Parquet on S3                                                 |

## Files of interest

- `backend/detections/*.yml`             — Sigma-style detection rules
- `backend/app/detection/engine.py`      — stateful engine
- `backend/app/detection/loader.py`      — YAML → Rule parser
- `backend/app/risk.py`                  — RBA score tracker
- `backend/app/ecs.py`                   — ECS event factory
- `backend/app/metrics.py`               — Prometheus exposition
- `backend/app/query/`                   — DSL lexer, parser, evaluator
- `backend/tests/test_detection.py`      — engine + risk tests (11 cases)
- `backend/tests/test_query_*.py`        — DSL lexer / parser / evaluator tests
- `docs/SCHEMA.md`                       — ECS ↔ OCSF ↔ CIM mapping
