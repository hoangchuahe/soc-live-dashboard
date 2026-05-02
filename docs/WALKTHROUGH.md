# Walkthrough — 5-minute demo script

> A guided tour of the project. Use this as the script for a take-home video,
> interview prep, or to onboard a curious reviewer who has never seen the repo.
>
> Each section is timed so the whole thing fits in 5–7 minutes.

---

## 0. Get it running (30 s)

```bash
git clone https://github.com/hoangchuahe/soc-live-dashboard
cd soc-live-dashboard
docker compose up --build
```

Open `http://localhost:3000`. Frames should start flowing within 2–3 seconds —
metrics will move, the geo map will populate with arcs, the alert feed will
start scrolling.

For the full demo with a real ElasticSearch + Kibana stack:

```bash
docker compose --profile elastic up --build
# Kibana → http://localhost:5601
# ES query → curl http://localhost:9200/soc-events/_search?pretty
```

---

## 1. Tour the dashboard (90 s)

Top to bottom, point at each panel and explain what's happening.

**Stats bar** — live numbers for CPU, memory, disk, network in/out, active
connections, **Detections fired**, alerts/hour. The "Detections" card
increments every time a Sigma rule actually fires — not just when an event
arrives.

**Attack Origin Map** (large, top-left) — D3 world map with great-circle arcs
from each attack source to a target marker over Ho Chi Minh City. Source
distribution is weighted to match realistic threat intel (CN 24%, RU 18%,
KP 6%, IR 5%). Source dot size scales with attack count; arc colour matches
severity.

**Network Topology** (top-right) — D3 force-directed graph: External →
Firewall → Core Switch → Servers + Edge Switch → Workstations. Each node
has a risk ring; high-risk nodes (>0.7) pulse red. Drag any node to
rearrange.

**System Metrics chart** (middle row) — D3 dual-line CPU and memory over the
last 60 seconds. Catmull-Rom curves, gradient area fill, end-dot pulse showing
the "now" frame.

**CVE Intel Feed** — pulled live from `nvd.nist.gov`'s public API. CVSS
scores, severity badges, click-through to the full NVD record. Cached
1 hour to respect rate limits.

**Event Timeline / Raw Logs** (tabbed, bottom-left) — D3 timeline OR raw
log lines in `winevent`, `syslog`, `cef`, or `netflow` format as they would
appear in a SIEM. Detected alerts appear as larger circles offset above the
timeline line.

**MITRE ATT&CK heatmap** (bottom-middle) — 13 tactics × event count.
Cells colour-graded by frequency.

**Top Risk Entities / Detection Rules** (tabbed, bottom-right) — Splunk-style
RBA score for hosts and IPs with progress bars; OR the 7 loaded rules with
their fire counts and last-fired timestamps.

**Live Alert Feed** (full-width, bottom) — combined raw events + rule-driven
alerts, severity-coded, with technique IDs visible.

---

## 2. Show detection engine in action (60 s)

Click the **Detection Rules** tab in the bottom-right panel. Watch the
"Authentication Brute Force" rule's fire count tick up — that means 5 failed
logins from the same source IP arrived within 60 seconds.

> The simulator deliberately drives ~30% of events through a 3-IP "active
> attacker" pool with brute-force / scanning behaviour, so threshold rules
> actually demo properly under load.

Switch to the **Top Risk Entities** tab — those same attacker IPs are at the
top of the ranking with high accumulated scores. If you wait a few minutes
without restarting, you'll see scores decay (30-minute half-life — Splunk's
RBA model).

This is the core of how a modern SOC operates: low-fidelity signals
contribute risk to the entity, the *entity* crosses the alert threshold, not
the rule.

---

## 3. Show the schema (60 s)

Open `http://localhost:8000/api/events?limit=1` in a browser.

The event comes back in **Elastic Common Schema** shape:

```jsonc
{
  "@timestamp": "2026-05-02T10:23:45Z",
  "event": {
    "id": "evt-823611",
    "kind": "event",
    "category": "authentication",
    "action": "auth_failure",
    "outcome": "failure",
    "severity": "high",
    "module": "winevent"
  },
  "source": {
    "ip": "203.0.113.42",
    "geo": { "country_name": "Russia",
             "location": { "lat": 61.5, "lon": 105.3 } }
  },
  "host":   { "name": "AUTH-SRV-01" },
  "user":   { "name": "administrator" },
  "threat": { "tactic":    { "name": "Credential Access" },
              "technique": { "id": "T1110.001",
                             "name": "Password Guessing" } },
  "log":    { "original": "[2026-05-02 10:23:45] EventID=4625 ..." },
  "message": "Repeated failed logon for account 'administrator'"
}
```

Now hit `/api/alerts` — same shape but `event.kind: "alert"` and extra
`rule.id` / `rule.name` fields. This is exactly how Elastic Security emits
its alerts, and how OCSF (the AWS/Splunk-backed open standard) structures
detection findings.

`docs/SCHEMA.md` shows how every field maps to OCSF and Splunk CIM, so a
real deployment could pipe these events straight into Splunk via SS-ECS
without any remapping.

---

## 4. Show a rule (45 s)

Open `backend/detections/auth_brute_force.yml`:

```yaml
title: Authentication Brute Force
id: rule-0001-auth-brute
detection:
  selection:
    event.category: authentication
    event.outcome: failure
  threshold:
    by: source.ip
    count: 5
    window_seconds: 60
mitre:
  tactic: Credential Access
  technique_id: T1110.001
  technique_name: Password Guessing
severity: high
risk_weight: 25
```

This is a **subset of the Sigma specification** — the open detection format
SIEM-agnostically used to share and version-control rules.

The pipeline:

1. `loader.py` parses YAML files into `Rule` objects at startup
2. `engine.py` evaluates every event against every rule
3. Threshold rules maintain per-`(rule, source.ip)` sliding windows in
   `collections.deque`
4. When a window crosses count, a `Detection` is emitted as an ECS event with
   `event.kind: alert` and the entity's risk score bumps by `risk_weight`

**To add a detection:** drop a new `.yml` in `backend/detections/`, restart
the backend. The rule appears in the UI panel and starts firing — no code
changes.

---

## 5. Show the tests (30 s)

```bash
cd backend
pytest
```

Output: **`11 passed in 0.13s`**

The two cases worth pointing at:

```python
def test_threshold_does_not_fire_below_count(engine):
    # 4 failed auths from same IP shouldn't fire (rule needs 5)
    for _ in range(4):
        detections = engine.evaluate(make_event("authentication", "auth_failure"))
        assert not [d for d in detections if d.rule_id == "rule-0001-auth-brute"]


def test_threshold_keyed_per_entity(engine):
    # 5 events split across 2 IPs should NOT fire
    for _ in range(3):
        engine.evaluate(make_event("authentication", "auth_failure", source_ip="1.1.1.1"))
    for _ in range(2):
        detections = engine.evaluate(make_event("authentication", "auth_failure", source_ip="2.2.2.2"))
    assert not [d for d in detections if d.rule_id == "rule-0001-auth-brute"]
```

These pin the behavioural contract of the engine — exactly what a real
detection-engineering team needs before they trust a rule in production.

---

## 6. Show the metrics endpoint (20 s)

`http://localhost:8000/metrics`:

```
# HELP soc_events_ingested_total Total raw events ingested
# TYPE soc_events_ingested_total counter
soc_events_ingested_total{category="authentication",severity="high"} 47
soc_events_ingested_total{category="network",severity="medium"} 23

# HELP soc_detections_fired_total Total detection rules that fired
# TYPE soc_detections_fired_total counter
soc_detections_fired_total{rule_id="rule-0001-auth-brute",tactic="Credential Access"} 3
```

Plain Prometheus exposition format — scrape with Prometheus, plot with
Grafana, alert with Alertmanager. Standard observability surface that any
SOC platform expects.

---

## 7. Show the architecture doc (30 s)

Open `docs/ARCHITECTURE.md`. Show the pipeline diagram (Simulator → Detection
Engine → Risk Tracker → ring buffer + ES + WebSocket).

Scroll to **"What's deliberately not in this build"**. List the
architectural patterns that would scale this to multi-host, multi-tenant
production:

- Redis pub/sub for WebSocket fan-out across API workers
- Kafka or NATS for ingestion with backpressure
- Detection rule CI (rule-as-code unit tests in CI)
- Alert lifecycle (acknowledged / in_progress / closed + assignee)
- Hot/warm/cold ES index lifecycle management

This is the question I'd expect from any architecture interview: "How would
you scale this?" — and the answer's already documented.

---

## Wrap (15 s)

The whole project is **~35 source files**, runs in one `docker compose up`,
has **11 green tests**, and demonstrates **ECS / Sigma / RBA / MITRE** —
the patterns real SIEMs use today.

Three repos worth of skills compressed into one demo:

1. Real-time WebSocket streaming + D3 visualisations (PNO SOC pattern)
2. Detection engineering with proper schema discipline (modern SIEM pattern)
3. Documented architecture decisions with deliberate scope limits
   (engineering maturity)
