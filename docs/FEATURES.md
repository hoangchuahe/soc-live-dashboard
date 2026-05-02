# Feature Catalogue

> Exhaustive feature inventory grouped by area, with file paths and rationale.
> Use this as: a reference, a checklist for "what skills does this prove",
> input for a comparison spreadsheet, or a fill-in for a technical-assessment
> form that asks "list the capabilities."

---

## Backend (FastAPI)

| Feature | File | Notes |
|---|---|---|
| Async WebSocket endpoint | `backend/app/main.py` | 1 Hz tick; broadcasts `{metrics, event, alerts[]}` per frame |
| Async REST surface (10 endpoints) | `backend/app/main.py` | See API table below |
| OpenAPI 3.1 auto-spec | FastAPI default | Live at `/docs` (Swagger UI) and `/redoc` |
| Health endpoint | `/health` | Reports ES status, rule count, buffer sizes |
| Lifespan-managed startup | FastAPI lifespan | ES init runs in background, never blocks app start |
| CORS middleware | `main.py` | Open by default for dev; tighten before prod |
| Structured event factory | `backend/app/ecs.py` | All events created through one ECS-shaped helper |

### REST API surface

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | service + ES + rule-count status |
| GET | `/metrics` | Prometheus exposition (counters + gauges) |
| GET | `/api/topology` | network nodes + edges |
| GET | `/api/events?since=<id>&limit=N` | ring-buffer events with replay cursor |
| GET | `/api/alerts` | ring-buffer of fired detections |
| GET | `/api/rules` | loaded Sigma rules + their fire counts |
| GET | `/api/risk/top?n=10` | top-N risky entities by RBA score |
| GET | `/api/cves` | live CVE feed from NVD |
| GET | `/api/mitre/tactics` | per-tactic event counts for the heatmap |
| GET | `/api/search?q=...` | ElasticSearch passthrough (if available) |
| WS | `/ws` | live frame stream |

---

## Detection engine

| Feature | File | Notes |
|---|---|---|
| Sigma-style YAML rules | `backend/detections/*.yml` | 7 rules covering 7 tactics |
| YAML rule loader | `backend/app/detection/loader.py` | Parses `selection`, `threshold`, `mitre` blocks |
| Stateful engine | `backend/app/detection/engine.py` | Per-`(rule, entity)` sliding window in `collections.deque` |
| Selection matching | `Rule.matches_selection()` | Walks dotted ECS paths (e.g. `source.ip`) |
| Threshold rules | YAML `threshold:` block | `count` events in `window_seconds` keyed `by` ECS field |
| Immediate-fire rules | rules without threshold | Fire on first selection match |
| Re-fire suppression | `engine._windows[].clear()` | After fire, window resets to avoid every-event spam |
| Rule fire counters | `Rule.fire_count` | Surfaced in `/api/rules` and the UI |
| Last-fired timestamp | `Rule.last_fired` | Per-rule freshness indicator |

### Loaded rules

| ID | Title | Tactic | Technique | Threshold |
|---|---|---|---|---|
| `rule-0001-auth-brute` | Authentication Brute Force | Credential Access | T1110.001 | 5 in 60 s |
| `rule-0002-port-scan` | Network Port Scan | Discovery | T1046 | 3 in 30 s |
| `rule-0003-lateral-rdp` | Suspicious Lateral Movement | Lateral Movement | T1021.001 | none |
| `rule-0004-c2-beacon` | Malware C2 Beacon Detected | Command and Control | T1071.001 | none |
| `rule-0005-policy-violation` | Security Policy Violation | Defense Evasion | T1562.001 | none |
| `rule-0006-exfil-volume` | Data Exfiltration — Anomalous Outbound | Exfiltration | T1041 | none |
| `rule-0007-web-exploit` | Web Exploitation Attempt | Initial Access | T1190 | none |

---

## Risk-Based Alerting

| Feature | File | Notes |
|---|---|---|
| Per-entity score tracker | `backend/app/risk.py` | Splunk-style RBA |
| Exponential decay | `_decay()` | 30-min half-life |
| Multi-rule contribution tracking | `Entity.contributing_rules` | Records which rules contributed to score |
| Top-N ranking | `RiskTracker.top()` | Returns sorted entity list with metadata |
| API endpoint | `/api/risk/top` | Powers `RiskPanel` UI |

---

## Schema (ECS)

| Feature | File | Notes |
|---|---|---|
| ECS event factory | `backend/app/ecs.py` | Centralised event construction |
| Nested ECS shape | All emitted events | `@timestamp`, `event.*`, `source.*`, `host.*`, `threat.*`, `log.*` |
| ECS field accessors (frontend) | `frontend/src/types/index.ts` | `ecs.severity()`, `ecs.country()`, `ecs.lat()`, etc. |
| Mapping doc | `docs/SCHEMA.md` | ECS ↔ OCSF ↔ Splunk CIM table |
| Distinct event vs alert kinds | `event.kind` field | `event` for raw, `alert` for detection-engine output |

---

## Threat intelligence

| Feature | File | Notes |
|---|---|---|
| Live CVE feed | `backend/app/threat_intel.py` | NVD public API, no auth required |
| 1-hour cache | `_cache + _fetched_at` | Respects rate limits (5 req / 30 s without key) |
| CVSS-to-severity mapping | `_cvss_to_severity()` | 9.0+ critical, 7+ high, 4+ medium |
| Frontend CVE panel | `frontend/src/components/CveFeed.tsx` | CVSS scores, click-through to nvd.nist.gov |

---

## Geo attribution

| Feature | File | Notes |
|---|---|---|
| Weighted source distribution | `backend/app/geo_data.py` | 14 countries with realistic threat-intel weights |
| World map | `frontend/src/components/GeoMap.tsx` | D3 `geoNaturalEarth1` projection |
| TopoJSON country fills | world-atlas via CDN | Lightweight (~90 KB), fetched once |
| Great-circle attack arcs | D3 GeoLineString + path | Source → HCMC target |
| Severity-coloured pulses | `SEV_COLOR` map | Source dot size scales with attack count |
| Zoom + pan | `d3.zoom()` | Mouse-wheel and drag |
| Country labels for hot sources | dynamic SVG text | Only labels >5 attacks |

---

## MITRE ATT&CK

| Feature | File | Notes |
|---|---|---|
| Technique-per-event mapping | `backend/app/simulator.py` `ACTION_MITRE` | Every event tagged at emit time |
| Technique catalogue | `backend/app/mitre_data.py` | 18 techniques across 13 tactics |
| Tactic heatmap | `frontend/src/components/MitrePanel.tsx` | Live per-tactic event counts |
| Per-rule tagging | YAML `mitre:` block | Carried into derived alerts (`event.kind: alert`) |
| Visible technique IDs | Alert feed, timeline tooltips | `T1110.001` style refs |

---

## ElasticSearch (optional)

| Feature | File | Notes |
|---|---|---|
| Async ES client | `backend/app/elastic.py` | `elasticsearch-py` v8 |
| Index mapping bootstrap | `_init()` | Creates `soc-events` with proper field types (`ip`, `keyword`, `text`, `date`) |
| Best-effort indexing | `asyncio.create_task()` | Never blocks WS tick |
| Graceful no-op when down | `is_available()` flag | App runs fine without ES |
| `/api/search` passthrough | `main.py` | Multi-match query against `message`, `host.name`, `source.ip`, etc. |
| Docker Compose profile | `docker-compose.yml` `profiles: [elastic]` | Optional ES + Kibana stack |
| Healthcheck-gated startup | ES service | curl-based, gates backend if profile active |

---

## Observability

| Feature | File | Notes |
|---|---|---|
| Prometheus exposition | `backend/app/metrics.py` | Plain text, no extra deps |
| `soc_events_ingested_total` | counter | Labelled by `category`, `severity` |
| `soc_detections_fired_total` | counter | Labelled by `rule_id`, `tactic` |
| `soc_websocket_clients` | gauge | Current connection count |
| `soc_uptime_seconds` | gauge | Process uptime |

---

## Replay & buffering

| Feature | File | Notes |
|---|---|---|
| Ring buffer (events) | `collections.deque(maxlen=500)` | In-memory, lightweight WAL |
| Ring buffer (alerts) | `collections.deque(maxlen=200)` | Separate stream for derived alerts |
| Replay cursor | `/api/events?since=<id>` | Reconnecting clients backfill without ES query |

---

## Frontend (React + D3)

| Feature | File | Notes |
|---|---|---|
| WebSocket hook | `frontend/src/hooks/useWebSocket.ts` | Auto-reconnect with 3 s backoff |
| Stats bar | `StatsCard.tsx` | 7 cards, danger flash for high CPU/Mem/criticals |
| Time-series chart | `MetricsChart.tsx` | D3 Catmull-Rom curves, gradient areas, end-dot pulses |
| Force-directed graph | `NetworkGraph.tsx` | Drag, zoom, pulsing risk rings |
| World map | `GeoMap.tsx` | Natural Earth projection, attack arcs |
| Event timeline | `EventTimeline.tsx` | D3 time-scaled axis, tooltips, alert offset |
| MITRE heatmap | `MitrePanel.tsx` | 13 tactics, colour-graded |
| Risk panel | `RiskPanel.tsx` | Top-N entities with score bars |
| Rules panel | `RulesPanel.tsx` | All rules with live fire counts and MITRE IDs |
| CVE feed | `CveFeed.tsx` | CVSS-coloured, click-through to nvd.nist.gov |
| Log viewer | `LogViewer.tsx` | Raw winevent / syslog / cef / netflow lines |
| Alert feed | `AlertFeed.tsx` | Combined events + alerts, severity badges, technique IDs |
| Tabbed panels | `App.tsx` | Timeline / Logs / Risk / Rules switchable |
| Tailwind dark theme | `index.css` | Monospace SOC aesthetic, scanline overlay, pulse-ring animation |
| ECS field accessor helpers | `types/index.ts` | `ecs.*` namespace flattens nested ECS for D3 components |

---

## Infrastructure

| Feature | File | Notes |
|---|---|---|
| Docker Compose | `docker-compose.yml` | One-command setup |
| Optional ES profile | `profiles: [elastic]` | ES 8.15 + Kibana via `--profile elastic` |
| Backend Dockerfile | `backend/Dockerfile` | Python 3.12-slim |
| Frontend Dockerfile | `frontend/Dockerfile` | Multi-stage Node build → nginx |
| nginx WS proxy | `frontend/nginx.conf` | Routes `/ws` to backend with `Upgrade` headers |
| ES healthcheck | docker-compose | curl-based |

---

## Tests

| Feature | File | Notes |
|---|---|---|
| Pytest config | `backend/pytest.ini` | Verbose, short tracebacks |
| 11 detection-engine tests | `backend/tests/test_detection.py` | Loader, selection, threshold, RBA |
| Test fixtures | `engine` pytest fixture | Fresh engine per test |
| Time-mocked decay test | `test_risk_decay_brings_score_down` | Forces `last_updated` into past |
| Per-entity keying test | `test_threshold_keyed_per_entity` | Pins multi-tenant correctness |

---

## Documentation

| Feature | File | Notes |
|---|---|---|
| README | `README.md` | Install, run, comparison-to-real-SIEMs table |
| Summary | `SUMMARY.md` | 1-page elevator pitch |
| Walkthrough | `docs/WALKTHROUGH.md` | 5-min demo script with timing cues |
| Features (this file) | `docs/FEATURES.md` | Exhaustive feature catalogue |
| Architecture | `docs/ARCHITECTURE.md` | Pipeline diagram, design rationale, deliberate omissions |
| Schema | `docs/SCHEMA.md` | ECS ↔ OCSF ↔ Splunk CIM mapping table |

---

## Skills demonstrated (CV mapping)

This table maps skills from my CV directly to where they show up in code, so a
reviewer can verify each claim by clicking a file path.

| Skill claim on CV | Where it shows up |
|---|---|
| Python / FastAPI | All backend code; lifespan, async endpoints, WebSocket |
| Async / WebSocket | `app/main.py:websocket_endpoint`; 1 Hz frame stream |
| Pytest | `backend/tests/test_detection.py` — 11 cases, all passing |
| React / TypeScript | All frontend code, strict tsconfig |
| D3.js (force-directed graph) | `NetworkGraph.tsx` — drag, zoom, risk rings |
| D3.js (timeline views) | `EventTimeline.tsx` — time-scaled axis, tooltips |
| D3.js (geospatial overlays) | `GeoMap.tsx` — Natural Earth projection, attack arcs |
| ElasticSearch | `app/elastic.py`; index mapping; `--profile elastic` |
| Docker / CI/CD | `docker-compose.yml` with profiles, multi-stage Dockerfiles |
| RESTful APIs | 10 endpoints with auto-OpenAPI |
| WebSocket streaming | `/ws` 1 Hz frame stream with auto-reconnect client |
| Real-time SOC dashboards | Whole project — direct mirror of the PNO work |
| AI tooling integration (CV: Outlier) | README "What I built vs what AI generated" section |
| Code review discipline | All commits made by `hoangchuahe` only; no AI co-authors |

---

## Comparison vs commercial SIEM

Reproduced from the README for self-contained reference.

| Capability | This project | Splunk ES | Elastic Security | Wazuh | MS Sentinel |
|---|:---:|:---:|:---:|:---:|:---:|
| ECS-shaped events | ✓ | — | ✓ | — | — |
| Sigma-style YAML detection rules | ✓ | ✓¹ | ✓¹ | — | — |
| Threshold / sliding-window detection | ✓ | ✓ | ✓ | ✓ | ✓ |
| MITRE ATT&CK tagging | ✓ | ✓ | ✓ | ✓ | ✓ |
| Risk-Based Alerting | ✓ | ✓ | ~² | — | ✓ |
| Real-time push to UI | ✓ (WS) | ✓ (XHR) | ✓ (XHR) | ✓ | ✓ |
| Real CVE / threat intel feed | ✓ NVD | ✓ | ✓ | — | ✓ |
| Geospatial attack map | ✓ | ✓ | ✓ | — | ✓ |
| Custom query language | — | SPL | KQL/EQL | — | KQL |
| Multi-tenant / RBAC | — | ✓ | ✓ | ✓ | ✓ |
| Distributed ingestion | — | ✓ | ✓ | ✓ | ✓ |

¹ via Sigma compilers (`pySigma`, Splunk app)
² Risk Engine in beta
