# SOC Live Dashboard

A real-time Security Operations Centre dashboard with **Sigma-style detection
rules**, **risk-based alerting**, and **ECS-formatted events** — built end-to-end
with FastAPI WebSockets, React, and D3.js.

This is a portfolio project that puts the architecture patterns I used at PNO
(real-time WebSocket ingestion, D3 force-graphs, geospatial overlays) on top of
the patterns real SIEMs use today (ECS schema, Sigma rules, threshold detection,
RBA risk scoring, Prometheus metrics).

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
| **Alert Feed** | Both raw events and rule-driven detections, severity-coded |

---

## How it compares to real SIEMs

| Capability                       | This project | Splunk ES | Elastic Security | Wazuh | Sentinel |
|----------------------------------|:------------:|:---------:|:----------------:|:-----:|:--------:|
| ECS-shaped events                |      ✓       |     —     |        ✓         |   —   |    —     |
| Sigma-style YAML detection rules |      ✓       |     ✓¹    |        ✓¹        |   —   |    —     |
| Threshold / sliding-window detection |  ✓       |     ✓     |        ✓         |   ✓   |    ✓     |
| MITRE ATT&CK tagging             |      ✓       |     ✓     |        ✓         |   ✓   |    ✓     |
| Risk-Based Alerting              |      ✓       |     ✓     |       ~²         |   —   |    ✓     |
| Real-time push to UI             |      ✓ (WS)  |   ✓ (XHR) |     ✓ (XHR)      |   ✓   |    ✓     |
| Real CVE/threat intel feed       |    ✓ NVD     |     ✓     |        ✓         |   —   |    ✓     |
| Geospatial attack map            |      ✓       |     ✓     |        ✓         |   —   |    ✓     |
| Custom query language            |      —       |     SPL   |    KQL/EQL       |   —   |   KQL    |
| Multi-tenant / RBAC              |      —       |     ✓     |        ✓         |   ✓   |    ✓     |
| Distributed ingestion            |      —       |     ✓     |        ✓         |   ✓   |    ✓     |

¹ via Sigma compilers (`pySigma`, Splunk app)
² via Risk Engine in beta

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

| Method | Path | What it returns |
|---|---|---|
| GET | `/health` | service + ES + rule-count status |
| GET | `/metrics` | Prometheus exposition (events_ingested, detections_fired, ws_clients) |
| GET | `/api/topology` | network nodes + edges |
| GET | `/api/events?since=<id>&limit=N` | ring-buffer events with replay cursor |
| GET | `/api/alerts` | ring-buffer of fired detections |
| GET | `/api/rules` | loaded Sigma rules + their fire counts |
| GET | `/api/risk/top?n=10` | top-N risky entities by RBA score |
| GET | `/api/cves` | live CVE feed from NVD |
| GET | `/api/mitre/tactics` | per-tactic event counts for the heatmap |
| GET | `/api/search?q=...` | ElasticSearch passthrough (if available) |
| WS  | `/ws` | live frame stream `{tick, metrics, event, alerts}` |

OpenAPI spec auto-generated at `/docs` (Swagger UI) and `/redoc`.

---

## Architecture & schema docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — pipeline diagram, why each
  piece is where it is, what's deliberately not built and how to add it
- [`docs/SCHEMA.md`](docs/SCHEMA.md) — ECS ↔ OCSF ↔ Splunk CIM field mapping

---

## What I built vs what AI generated

The architecture, the Sigma rule format, the detection engine, the RBA decay
model, the ECS schema decision — those are mine. AI was used to generate
boilerplate (Pydantic schemas, D3 axis setup, Docker config, Tailwind classes)
and accelerate the typing-out part. Every file was reviewed before commit, and
the test suite was written *first* for the detection engine to pin its
contract before the implementation evolved.

The places the AI's first attempt was wrong and got rewritten:

- The geo projection initially returned `null` for some coordinates without
  guarding — fixed with explicit `if (!targetXY) return` checks
- The ring-buffer replay endpoint was originally a list slice; rewrote to a
  cursor-based scan so reconnecting clients don't double-receive events
- Detection-engine state was initially per-rule (global); rewrote keyed by
  `(rule_id, entity)` so two attackers don't collide in one window

---

## About

Built by **Pham Nhat Hoang** — full-stack engineer specialising in Python
back-end systems and React/D3 frontends.

- Email: phamnhathoang091@gmail.com
- GitHub: [github.com/hoangchuahe](https://github.com/hoangchuahe)
