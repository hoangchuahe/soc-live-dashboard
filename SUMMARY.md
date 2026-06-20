# Project Summary

> One-page elevator pitch — for LinkedIn posts, application cover letters,
> recruiters who give 30 seconds, GitHub topic blurbs.

## What it is

A real-time **Security Operations Centre dashboard** with a working detection
engine, risk-based alerting, and ECS-formatted events — built end-to-end with
FastAPI + WebSocket on the back, React + D3.js on the front.

This is **not** a wrapper around an existing SIEM. The detection engine,
risk model, schema, and visualisations are implemented from scratch. The
patterns mirror how **Splunk Enterprise Security**, **Elastic Security**, and
**Microsoft Sentinel** actually work day-to-day.

## Why this project

Three things converge:

1. **Showcase real-time WebSocket + D3 visualisations** — the strongest, rarest
   skill on my CV (built at PNO's SOC, with custom force-directed graphs,
   timeline views, and geospatial overlays)
2. **Demonstrate SIEM / detection-engineering domain depth** — ECS schema,
   Sigma rule format, MITRE ATT&CK mapping, Risk-Based Alerting
3. **Prove I can drive a system from architecture decisions through to
   running, tested code** — not just a tutorial copy-paste

## Standout features

- **7 Sigma-style YAML detection rules** covering brute force, port scan,
  lateral movement, C2 beacon, exfiltration, exploitation, policy violation
- **Stateful detection engine** with sliding-window thresholds, keyed
  per-entity, with 11 unit tests pinning behaviour
- **Risk-Based Alerting** — entities accumulate score from rule weights with
  exponential decay (30-min half-life), Splunk RBA-style
- **ECS schema everywhere** — events flow in Elastic Common Schema shape,
  mapping cleanly to OCSF and Splunk CIM
- **Real CVE feed** pulled live from the NVD public API
- **D3 attack origin map** — great-circle arcs from realistic threat-intel
  weighted source countries (CN 24%, RU 18%, KP 6%, IR 5%, ...)
- **Prometheus `/metrics` endpoint** with proper labelled counters
- **Optional ElasticSearch + Kibana** stack via Docker Compose profile

## Tech stack

Python 3.12 / FastAPI · React 18 / TypeScript · D3.js v7 · ElasticSearch (optional) · Tailwind CSS · Docker Compose

## Numbers

| | |
|---|---|
| Source files | ~35 (backend + frontend + rules + tests + docs) |
| Sigma-style YAML rules | 7 base + 1 correlation |
| Tests | 214 passing (186 Pytest + 28 Vitest) |
| MITRE ATT&CK tactics tracked | 13 |
| Weighted attack-source countries | 14 |
| Dashboard panels | 9 |
| API endpoints | 10 (1 WebSocket + 9 REST) |

## Run it

```bash
git clone https://github.com/hoangchuahe/soc-live-dashboard
cd soc-live-dashboard
docker compose up --build
# → http://localhost:3000
```

With ElasticSearch + Kibana:

```bash
docker compose --profile elastic up --build
# Kibana on :5601, ES on :9200
```

## Quick links

- [README.md](README.md) — install, run, full comparison-to-real-SIEMs table
- [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md) — 5-minute guided demo script
- [docs/FEATURES.md](docs/FEATURES.md) — exhaustive feature catalogue
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — pipeline + design rationale
- [docs/SCHEMA.md](docs/SCHEMA.md) — ECS ↔ OCSF ↔ Splunk CIM field mapping

## Built by

**Pham Nhat Hoang** — full-stack engineer specialising in Python back-end
systems and React/D3 frontends. 3+ years production experience including
PNO's Security Operations Centre and AXA Abiaka. Reachable at
[phamnhathoang091@gmail.com](mailto:phamnhathoang091@gmail.com).
