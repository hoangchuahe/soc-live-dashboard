# Schema mapping — ECS · OCSF · Splunk CIM

This dashboard emits events conforming to the **Elastic Common Schema (ECS)**.
ECS is the most widely adopted security telemetry schema and translates cleanly to
OCSF (the OASIS open standard pushed by AWS / Splunk / Cloudflare) and to Splunk's
internal Common Information Model (CIM).

Adopting a standard schema means a downstream Elastic Security, Splunk via SS-ECS,
or Wazuh deployment can ingest these events without remapping.

## Field mapping

| ECS (this project)                  | OCSF (1.x)                              | Splunk CIM           |
|-------------------------------------|------------------------------------------|----------------------|
| `@timestamp`                        | `time`                                  | `_time`              |
| `event.id`                          | `metadata.uid`                          | `event_id`           |
| `event.kind` ∈ {event, alert}       | `metadata.event_code`                   | `tag`                |
| `event.category`                    | `category_name` / `class_name`          | datamodel name       |
| `event.action`                      | `activity_name`                         | `action`             |
| `event.outcome` ∈ {success,failure} | `status` / `disposition_id`             | `result` / `action`  |
| `event.severity`                    | `severity` (numeric 0-6)                | `severity_id`        |
| `event.module`                      | `metadata.product.feature.name`         | `sourcetype`         |
| `source.ip`                         | `src_endpoint.ip`                       | `src_ip` / `src`     |
| `source.geo.country_name`           | `src_endpoint.location.country`         | `src_country`        |
| `source.geo.location.lat/lon`       | `src_endpoint.location.coordinates`     | `src_lat`, `src_lon` |
| `destination.ip`                    | `dst_endpoint.ip`                       | `dest_ip` / `dest`   |
| `host.name`                         | `device.name` / `device.hostname`       | `host`               |
| `user.name`                         | `actor.user.name`                       | `user`               |
| `process.name`                      | `actor.process.name`                    | `process`            |
| `threat.tactic.name`                | `attacks.tactic.name`                   | `mitre_tactic`       |
| `threat.technique.id`               | `attacks.technique.uid`                 | `mitre_technique_id` |
| `threat.technique.name`             | `attacks.technique.name`                | `mitre_technique`    |
| `rule.id`                           | `metadata.correlation_uid`              | `rule_id`            |
| `rule.name`                         | `finding.title`                         | `signature`          |
| `log.original`                      | `raw_data`                              | `_raw`               |
| `message`                           | `message`                               | `message`            |

## Event vs alert

ECS distinguishes raw events (`event.kind: event`) from derived alerts produced by
the detection engine (`event.kind: alert`). Alerts carry the extra `rule.*` fields
identifying which detection rule fired.

```jsonc
// Raw event
{
  "@timestamp": "2026-05-02T10:23:45Z",
  "event": { "kind": "event", "category": "authentication", "action": "auth_failure", "severity": "high" },
  "source": { "ip": "203.0.113.42", "geo": { "country_name": "Russia" } },
  "host": { "name": "AUTH-SRV-01" },
  "message": "Failed logon for user 'admin'"
}

// Derived alert (after threshold met)
{
  "@timestamp": "2026-05-02T10:23:50Z",
  "event":  { "kind": "alert", "category": "detection", "severity": "high" },
  "rule":   { "id": "rule-0001-auth-brute", "name": "Authentication Brute Force" },
  "threat": { "tactic": { "name": "Credential Access" }, "technique": { "id": "T1110.001" } },
  "entity": "203.0.113.42",
  "matched_count": 5,
  "triggering_event_id": "evt-823611",
  "message": "Authentication Brute Force — entity=203.0.113.42 (count=5 in 60s)"
}
```

## References

- ECS: https://www.elastic.co/guide/en/ecs/current/
- OCSF: https://schema.ocsf.io/
- Splunk CIM: https://docs.splunk.com/Documentation/CIM/latest/User/Overview
