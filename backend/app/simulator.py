import random
from datetime import datetime, timezone
from .models import SecurityEvent, NetworkNode, NetworkEdge

_cpu = 45.0
_mem = 62.0
_tick = 0

_EVENT_TYPES = [
    "AUTH_FAILURE",
    "PORT_SCAN",
    "ANOMALY",
    "INTRUSION_ATTEMPT",
    "POLICY_VIOLATION",
    "MALWARE_DETECTED",
    "LATERAL_MOVEMENT",
]
_SEVERITIES = ["low", "low", "medium", "medium", "high", "critical"]
_SOURCES = [f"10.0.{r}.{h}" for r in range(1, 6) for h in range(2, 20)]
_INTERNAL = [f"192.168.1.{i}" for i in range(10, 50)]
_MESSAGES = [
    "Multiple failed login attempts detected",
    "Unusual port scan from external host",
    "Anomalous outbound data volume spike",
    "Potential brute-force attack on SSH",
    "Policy violation: unauthorized lateral move",
    "Suspicious process spawned on workstation",
    "Malware signature match in memory",
    "Unusual protocol usage on internal segment",
]


def _walk(current: float, lo: float, hi: float, step: float) -> float:
    current += random.uniform(-step, step)
    return round(max(lo, min(hi, current)), 1)


def next_metrics() -> dict:
    global _cpu, _mem
    _cpu = _walk(_cpu, 5, 95, 3)
    _mem = _walk(_mem, 20, 92, 1.5)
    return {
        "cpu_percent": _cpu + round(random.uniform(-1, 1), 1),
        "memory_percent": _mem + round(random.uniform(-0.5, 0.5), 1),
        "disk_percent": round(random.uniform(52, 58), 1),
        "network_in_mbps": round(random.uniform(8, 240), 1),
        "network_out_mbps": round(random.uniform(4, 120), 1),
        "active_connections": random.randint(60, 450),
        "alerts_last_hour": random.randint(4, 95),
    }


def maybe_event() -> SecurityEvent | None:
    if random.random() > 0.18:
        return None
    return SecurityEvent(
        id=f"evt-{random.randint(100_000, 999_999)}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        type=random.choice(_EVENT_TYPES),
        severity=random.choice(_SEVERITIES),
        source_ip=random.choice(_SOURCES),
        destination_ip=random.choice(_INTERNAL) if random.random() > 0.3 else None,
        message=random.choice(_MESSAGES),
        count=random.randint(1, 60),
    )


def get_topology() -> tuple[list[NetworkNode], list[NetworkEdge]]:
    nodes = [
        NetworkNode(id="ext-1", label="External", type="external", risk=0.92),
        NetworkNode(id="fw-1", label="Firewall", type="firewall", risk=0.18),
        NetworkNode(id="sw-core", label="Core Switch", type="switch", risk=0.10),
        NetworkNode(id="sw-edge", label="Edge Switch", type="switch", risk=0.14),
        NetworkNode(id="srv-web", label="Web Server", type="server", risk=0.58),
        NetworkNode(id="srv-db", label="DB Server", type="server", risk=0.28),
        NetworkNode(id="srv-auth", label="Auth Server", type="server", risk=0.42),
        NetworkNode(id="wks-1", label="WKS-001", type="workstation", risk=0.72),
        NetworkNode(id="wks-2", label="WKS-002", type="workstation", risk=0.21),
        NetworkNode(id="wks-3", label="WKS-003", type="workstation", risk=0.87),
        NetworkNode(id="wks-4", label="WKS-004", type="workstation", risk=0.15),
    ]
    edges = [
        NetworkEdge(source="ext-1", target="fw-1"),
        NetworkEdge(source="fw-1", target="sw-core"),
        NetworkEdge(source="sw-core", target="sw-edge"),
        NetworkEdge(source="sw-core", target="srv-web"),
        NetworkEdge(source="sw-core", target="srv-db"),
        NetworkEdge(source="sw-core", target="srv-auth"),
        NetworkEdge(source="sw-edge", target="wks-1"),
        NetworkEdge(source="sw-edge", target="wks-2"),
        NetworkEdge(source="sw-edge", target="wks-3"),
        NetworkEdge(source="sw-edge", target="wks-4"),
    ]
    return nodes, edges
