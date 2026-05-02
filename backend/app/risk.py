"""
Risk-Based Alerting (RBA) — entity risk scoring.

Each entity (host, user, IP) accumulates risk weight every time a detection
rule fires against it. Scores decay linearly over time so an entity that
stops misbehaving fades from the top-N list.

Inspired by Splunk's RBA: https://www.splunk.com/en_us/blog/security/risk-based-alerting.html
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

DECAY_HALF_LIFE_SECONDS = 30 * 60  # 30 minutes


@dataclass
class Entity:
    name: str
    score: float = 0.0
    last_updated: float = field(default_factory=time.time)
    contributing_rules: dict[str, int] = field(default_factory=dict)  # rule_id → fire count


class RiskTracker:
    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}

    def bump(self, entity_name: str, weight: int, rule_id: str) -> None:
        ent = self._get(entity_name)
        self._decay(ent)
        ent.score += weight
        ent.last_updated = time.time()
        ent.contributing_rules[rule_id] = ent.contributing_rules.get(rule_id, 0) + 1

    def top(self, n: int = 10) -> list[dict[str, Any]]:
        # decay everyone before sorting so display is always up-to-date
        for ent in self._entities.values():
            self._decay(ent)

        ranked = sorted(self._entities.values(), key=lambda e: e.score, reverse=True)
        return [
            {
                "name": e.name,
                "score": round(e.score, 1),
                "rule_count": len(e.contributing_rules),
                "last_updated_seconds_ago": round(time.time() - e.last_updated, 1),
            }
            for e in ranked[:n]
            if e.score > 0
        ]

    def _get(self, name: str) -> Entity:
        if name not in self._entities:
            self._entities[name] = Entity(name=name)
        return self._entities[name]

    def _decay(self, ent: Entity) -> None:
        elapsed = time.time() - ent.last_updated
        if elapsed <= 0 or ent.score <= 0:
            return
        # exponential decay: score *= 0.5 ** (elapsed / half_life)
        factor = 0.5 ** (elapsed / DECAY_HALF_LIFE_SECONDS)
        ent.score *= factor
        ent.last_updated = time.time()
