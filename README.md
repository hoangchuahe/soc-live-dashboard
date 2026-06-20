# SOC Live Dashboard

[![CI](https://github.com/hoangchuahe/soc-live-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/hoangchuahe/soc-live-dashboard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6.svg)](https://www.typescriptlang.org/)
[![Tests](https://img.shields.io/badge/tests-231%20passing-brightgreen.svg)](backend/tests)

**🔗 Live demo:** [soc-live-dashboard.fly.dev](https://soc-live-dashboard.fly.dev) — log in with `admin` / `admin` (admin) or `viewer` / `viewer` (read-only). Runs in simulator mode; data resets on redeploy.

A real-time Security Operations Centre dashboard with **Sigma-style detection
rules**, **risk-based alerting**, **JWT auth + RBAC**, and **ECS-formatted events**
— built end-to-end with FastAPI WebSockets, React, and D3.js.

This is a portfolio project that puts the architecture patterns I used at PNO
(real-time WebSocket ingestion, D3 force-graphs, geospatial overlays) on top of
the patterns real SIEMs use today (ECS schema, Sigma rules, threshold detection,
RBA risk scoring, Prometheus metrics).

> **📸 Screenshot/GIF goes here** — record a 5-second clip of the running dashboard
> with `OBS Studio` or `ScreenToGif`, save as `docs/screenshot.png` or
> `docs/demo.gif`, and replace this placeholder. Recommended: include the geo
> map with arcs firing + a few alerts scrolling in the feed.
>
> ```markdown
> ![SOC Live Dashboard](docs/demo.gif)
> ```

---

## What it shows

| Panel | What's happening |
|---|---|
| **Stats bar** | Live CPU, memory, disk, network I/O, connections, **detections fired** |
| **Attack Origin Map** | D3 world map with great-circle arcs from CN/RU/KP/IR/US → HCMC |
| **Network Topology** | D3 force-directed graph; risk rings pulse on high-risk assets |
| **Metrics chart** | D3 dual-line CPU/memory time-series, 60-second rolling buffer |
| **CVE Intel Feed** | Live pull from the **NVD public API**, CVSS scores, click-through to nvd.nist.gov |
| **Event Timeline / Raw Logs** | D3 time-axis OR raw `winevent / syslog / cef / netflow` log lines |
| **MITRE ATT&CK heatmap** | 13 tactics × event count — events tagged with technique IDs |
| **Top Risk Entities** | Splunk-style RBA: hosts/IPs ranked by accumulated risk score |
| **Detection Rules** | Sigma YAML rules + their fire counts, last-fired, threshold flag |
| **Alert Feed** | Raw events, rule-driven detections, and **multi-stage correlated alerts** (kill-chain), severity-coded |

---

## How it compares to real SIEMs

| Capability                           | This project | Splunk ES | Elastic Security | Wazuh | Sentinel |
|--------------------------------------|:------------:|:---------:|:----------------:|:-----:|:--------:|
| ECS-shaped events                    |      ✓       |     —     |        ✓         |   —   |    —     |
| Sigma-style YAML detection rules³    |      ✓       |     ✓¹    |        ✓¹        |   —   |    —     |
| Threshold / sliding-window detection |      ✓       |     ✓     |        ✓         |   ✓   |    ✓     |
| Multi-stage correlation              |      ✓       |     ✓     |        ✓         |   ~   |    ✓     |
| MITRE ATT&CK tagging                 |      ✓       |     ✓     |        ✓         |   ✓   |    ✓     |
| Risk-Based Alerting                  |      ✓       |     ✓     |       ~²         |   —   |    ✓     |
| Real-time push to UI                 |      ✓ (WS)  |   ✓ (XHR) |     ✓ (XHR)      |   ✓   |    ✓     |
| Real CVE / threat intel feed         |    ✓ NVD     |     ✓     |        ✓         |   —   |    ✓     |
| Geospatial attack map                |      ✓       |     ✓     |        ✓         |   —   |    ✓     |
| JWT auth + RBAC                      |      ✓       |     ✓     |        ✓         |   ✓   |    ✓     |
| Alert lifecycle (ack / close)        |      ✓       |     ✓     |        ✓         |   ✓   |    ✓     |
| Persistent storage                   |   ✓ SQLite   |  ✓ index  |     ✓ index      | ✓ index | ✓ LA  |
| Custom query language                |     ✓⁴       |     SPL   |    KQL/EQL       |   —   |   KQL    |
| Multi-tenant / RBAC                  |      —       |     ✓     |        ✓         |   ✓   |    ✓     |
| Distributed ingestion                |      —       |     ✓     |        ✓         |   ✓   |    ✓     |

¹ via Sigma compilers (`pySigma`, Splunk app)
² via Risk Engine in beta
³ This project ships 7 example rules — not a comparable corpus to Splunk ESCU's hundreds
⁴ a substring / field / numeric DSL (`AND`/`OR`/`NOT`) with a Discover view — intentionally simpler than SPL/KQL

The detection-engine, RBA, and ECS pieces are the *substance* — the rest of the
gap (multi-tenant, distributed) is intentionally out of scope. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for what's deliberately omitted
and how it would be added.

---

## Detection rules — Sigma-style YAML

Rules live in [`backend/detections/`](backend/detections) and are loaded at
startup:

```yaml
# backend/detections/auth_brute_force.yml
title: Authentication Brute Force
id: rule-0001-auth-brute
description: Multiple failed authentication attempts from a single source.

logsource:
  category: authentication

detection:
  selection:
    event.category: authentication
    event.outcome: failure
  threshold:
    by: source.ip
    count: 5
    window_seconds: 60
  condition: selection AND threshold

mitre:
  tactic: Credential Access
  technique_id: T1110.001
  technique_name: Password Guessing

severity: high
risk_weight: 25
```

Engine semantics — implemented in
[`backend/app/detection/engine.py`](backend/app/detection/engine.py):

- `selection` — a flat ECS-field-path → expected-value match
- `threshold` — sliding window keyed by an ECS field (`source.ip`, `host.name`)
- On fire: emit a derived ECS event with `event.kind: alert`, bump the entity's risk score

11 unit tests cover loader, selection matching, threshold semantics, per-entity
keying, and risk decay:

```bash
cd backend
pytest          # → 11 passed
```

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (Python 3.12) | Async-first WebSocket; auto OpenAPI |
| Schema | **ECS** (Elastic Common Schema) | Industry standard; translates to OCSF / Splunk CIM |
| Detection | **Custom engine + Sigma-style YAML** | Stateful sliding windows; pluggable rules |
| Risk model | **Splunk-style RBA** | Exponential decay, 30-min half-life |
| Threat intel | **NVD public API** | Real CVEs, no auth, hourly cache |
| Storage (optional) | **ElasticSearch 8.15** | Best-effort indexing; `--profile elastic` |
| Metrics | **Prometheus exposition** | `/metrics` endpoint, counters + gauges |
| Frontend | **React 18 + TypeScript + D3.js** | Custom force-graph, time-series, geo projection |
| Styling | **Tailwind CSS** | Dark monospace SOC theme |
| Infra | **Docker Compose** | One command; ES + Kibana behind a profile |

---

## Quick start

### Docker (recommended)

```bash
git clone https://github.com/hoangchuahe/soc-live-dashboard.git
cd soc-live-dashboard
docker compose up --build
# → dashboard at http://localhost:3000
```

With the optional ElasticSearch + Kibana stack:

```bash
docker compose --profile elastic up --build
# → dashboard      http://localhost:3000
# → kibana         http://localhost:5601
# → ES query       curl http://localhost:9200/soc-events/_search?pretty
```

### Local dev

```bash
# backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# tests
pytest

# frontend (separate terminal)
cd frontend
npm install
npm run dev   # → http://localhost:5173
```

---

## API surface

Public (no auth):

| Method | Path | What it returns |
|---|---|---|
| GET | `/health` | service + ES + rule-count + DB status |
| GET | `/metrics` | Prometheus exposition (events_ingested, detections_fired, ws_clients) |
| GET | `/api/topology` | network nodes + edges |
| GET | `/api/events?since=<id>&limit=N` | ring-buffer events with replay cursor |
| GET | `/api/alerts` | ring-buffer of fired detections |
| GET | `/api/alerts/lifecycle?status=...` | alert workflow status (new / ack / in_progress / closed) |
| GET | `/api/rules` | loaded Sigma rules + their fire counts |
| GET | `/api/risk/top?n=10` | top-N risky entities by RBA score |
| GET | `/api/cves` | live CVE feed from NVD |
| GET | `/api/mitre/tactics` | per-tactic event counts for the heatmap |
| GET | `/api/search?q=...` | ElasticSearch passthrough (if available) |
| POST | `/api/auth/login` | exchange `{username, password}` for JWT |
| WS  | `/ws` | live frame stream `{tick, metrics, event, alerts}` |

Authenticated (Bearer token from `/api/auth/login`):

| Method | Path | Required role | What it does |
|---|---|---|---|
| GET  | `/api/auth/me` | any | current user info |
| POST | `/api/alerts/{id}/ack` | any | acknowledge an alert (Tier 1 analyst workflow) |
| POST | `/api/alerts/{id}/close` | **admin** | close an alert (Tier 2 / admin workflow) |
| POST | `/api/rules/reload` | **admin** | hot-reload Sigma YAML rules from disk |
| POST | `/api/admin/prune?days=N` | **admin** | delete events older than N days |

OpenAPI spec auto-generated at `/docs` (Swagger UI) and `/redoc`.

### Querying events — the DSL

Open the **Discover** view from the header toolbar to search events with a live
event histogram and a results table. Each alert in the feed also has a pivot
button that jumps straight to Discover pre-filled with `source.ip:"…"`. The same
query language drives `/api/search`:

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

### Demo credentials

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "admin"}'
# → {"access_token": "eyJhbGc...", "role": "admin", "expires_in": 28800}

# Use the token:
curl -H 'Authorization: Bearer eyJhbGc...' http://localhost:8000/api/auth/me
```

Override credentials via env vars `ADMIN_PASSWORD`, `VIEWER_PASSWORD`,
`JWT_SECRET` before deploying.

---

## Deployment (Fly.io)

Deployed as a single container: a multi-stage `Dockerfile` builds the React SPA
and FastAPI serves it alongside the API and WebSocket — one origin, no nginx.
Runs in `SOC_MODE=demo` (simulator); SQLite is ephemeral.

```bash
# install flyctl, then from the repo root:
fly auth login
fly apps create soc-live-dashboard            # pick a free name if taken
fly secrets set JWT_SECRET="$(openssl rand -hex 32)"
fly deploy                                    # uses fly.toml + Dockerfile
fly open                                       # opens the live URL
```

Demo credentials are intentionally public (`admin`/`admin`, `viewer`/`viewer`).
`JWT_SECRET` is set to a random value so tokens can't be forged against the
default. The app scales to zero when idle and wakes in ~1-3s on the next request.

---

## Architecture & schema docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — pipeline diagram, why each
  piece is where it is, what's deliberately not built and how to add it
- [`docs/SCHEMA.md`](docs/SCHEMA.md) — ECS ↔ OCSF ↔ Splunk CIM field mapping

---

## How I worked with AI tooling

The architectural decisions here are mine: choosing ECS as the schema baseline
over OCSF, picking sliding-window threshold detection over batch correlation,
the per-`(rule, entity)` state keying, the Splunk-style RBA decay model. I
have an LLM-evaluation background (Outlier / Scale AI) so I treat AI output as
a first draft and a typing accelerator — never as a finished design.

Where AI was used effectively:

- Boilerplate generation — Pydantic models, D3 axis scaffolding, Docker config,
  Tailwind classes, FastAPI endpoint stubs
- Translating between specs — looking up ECS field names, OCSF mappings, MITRE
  technique IDs

Where I owned the work directly:

- The pipeline shape (Simulator → Engine → RiskTracker → ring buffer → WS) and
  the decision to keep state in-process for this scope
- The Sigma-subset YAML format and the loader that parses it
- The detection-engine contract (`evaluate(event) → list[Detection]`) and the
  per-rule unit tests pinning that contract
- The RBA decay maths (exponential, 30-min half-life)
- All trade-off documentation in `docs/ARCHITECTURE.md` ("what's deliberately
  not in this build")

---

## About

Built by **Pham Nhat Hoang** — full-stack engineer specialising in Python
back-end systems and React/D3 frontends.

- Email: phamnhathoang091@gmail.com
- GitHub: [github.com/hoangchuahe](https://github.com/hoangchuahe)
