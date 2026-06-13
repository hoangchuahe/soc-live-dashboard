"""
Elastic Common Schema (ECS) event factory.

ECS is the de-facto field-naming standard for security telemetry. Adopting
it means SIEM products (Elastic, Splunk via SS-ECS, OCSF translations) can
ingest these events without remapping. Spec: https://www.elastic.co/guide/en/ecs/current/

The dashboard emits events in ECS shape:

    {
      "@timestamp": "...",
      "event":  {"id", "kind", "category", "action", "outcome", "severity", "module"},
      "source": {"ip", "geo": {"country_name", "location": {"lat", "lon"}}},
      "destination": {"ip"},
      "host":   {"name"},
      "user":   {"name"},
      "process": {"name"},
      "threat": {"tactic": {"name"}, "technique": {"id", "name"}},
      "rule":   {"id", "name"},   # populated only on alerts
      "log":    {"original", "level"},
      "message": "..."
    }
"""

from __future__ import annotations

from typing import Any


def make_event(
    *,
    event_id: str,
    timestamp: str,
    category: str,
    action: str,
    outcome: str,
    severity: str,
    module: str,
    message: str,
    source_ip: str | None = None,
    source_country: str | None = None,
    source_lat: float | None = None,
    source_lon: float | None = None,
    destination_ip: str | None = None,
    host_name: str | None = None,
    user_name: str | None = None,
    process_name: str | None = None,
    tactic: str | None = None,
    technique_id: str | None = None,
    technique_name: str | None = None,
    log_original: str | None = None,
    provenance: str = "live",
    dataset: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evt: dict[str, Any] = {
        "@timestamp": timestamp,
        "event": {
            "id": event_id,
            "kind": "event",
            "category": category,
            "action": action,
            "outcome": outcome,
            "severity": severity,
            "module": module,
        },
        "message": message,
    }

    if dataset:
        evt["event"]["dataset"] = dataset

    if source_ip:
        src: dict[str, Any] = {"ip": source_ip}
        if source_country and source_lat is not None and source_lon is not None:
            src["geo"] = {
                "country_name": source_country,
                "location": {"lat": source_lat, "lon": source_lon},
            }
        evt["source"] = src

    if destination_ip:
        evt["destination"] = {"ip": destination_ip}
    if host_name:
        evt["host"] = {"name": host_name}
    if user_name:
        evt["user"] = {"name": user_name}
    if process_name:
        evt["process"] = {"name": process_name}
    if technique_id:
        evt["threat"] = {
            "tactic":    {"name": tactic} if tactic else None,
            "technique": {"id": technique_id, "name": technique_name},
        }
    if log_original:
        evt["log"] = {"original": log_original, "level": severity}

    if provenance == "simulated":
        evt["labels"] = {"provenance": provenance}

    if extra:
        evt.update(extra)

    return evt
