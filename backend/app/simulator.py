"""
SOC event simulator — emits events in Elastic Common Schema (ECS) shape.

Field naming follows ECS so events can be ingested by Elastic Security,
Splunk (via SS-ECS), or translated to OCSF without remapping.
"""

import random
from datetime import datetime, timezone

from .ecs import make_event
from .geo_data import random_source

_cpu = 45.0
_mem = 62.0

# ── Realistic host inventory ──────────────────────────────────────────────────
_HOSTNAMES = [
    "DC01.corp.local", "WEB-PROD-01", "DB-MYSQL-02", "AUTH-SRV-01",
    "WKS-HOANG-01",   "WKS-ALICE-02", "WKS-BOB-03",  "JUMP-SRV-01",
    "BACKUP-SRV-01",  "MON-ELK-01",
]

_USERS = ["administrator", "svc_backup", "j.smith", "a.nguyen", "h.pham", "guest", "root"]

_PROCESSES_BY_MODULE = {
    "winevent": ["lsass.exe", "powershell.exe", "cmd.exe", "svchost.exe",
                 "rundll32.exe", "mshta.exe", "wscript.exe"],
    "syslog":   ["/usr/sbin/sshd", "/bin/bash", "sudo", "cron", "nginx", "python3"],
    "cef":      ["AV-Engine", "IDS-Snort", "Firewall-FW01", "WAF-ModSec"],
    "netflow":  [],
}

_INTERNAL_IPS = [f"192.168.{s}.{h}" for s in (1, 2, 10) for h in range(10, 50)]

# A small pool of "active attacker" IPs that get reused so threshold-based
# detection rules (e.g. brute force, port scan) actually fire under demo load.
_ATTACKER_IPS = [
    "203.0.113.42", "198.51.100.17", "45.142.65.93",
]

# Map our domain event "actions" to ECS categories
# event.category ∈ ECS allowed values: authentication, network, intrusion_detection,
#                  malware, configuration, file, process, ...
ACTION_TEMPLATE = {
    "auth_failure":       ("authentication", "failure", "winevent"),
    "scan":               ("network",        "unknown", "netflow"),
    "anomaly":            ("network",        "unknown", "syslog"),
    "intrusion_attempt":  ("intrusion_detection", "failure", "cef"),
    "policy_violation":   ("configuration",  "success", "winevent"),
    "beacon":             ("malware",        "success", "cef"),
    "lateral_movement":   ("authentication", "success", "winevent"),
}

# MITRE ATT&CK technique per action
ACTION_MITRE = {
    "auth_failure":      ("Credential Access",     "T1110.001", "Password Guessing"),
    "scan":              ("Discovery",             "T1046",     "Network Service Discovery"),
    "anomaly":           ("Exfiltration",          "T1041",     "Exfiltration Over C2 Channel"),
    "intrusion_attempt": ("Initial Access",        "T1190",     "Exploit Public-Facing Application"),
    "policy_violation":  ("Defense Evasion",       "T1562.001", "Disable Security Tools"),
    "beacon":            ("Command and Control",   "T1071.001", "Web Protocols C2"),
    "lateral_movement":  ("Lateral Movement",      "T1021.001", "Remote Desktop Protocol"),
}

# Windows Event IDs commonly seen for each action
WIN_EVENT_IDS = {
    "auth_failure":      4625,
    "lateral_movement":  4648,
    "policy_violation":  4719,
    "anomaly":           4688,
    "intrusion_attempt": 4625,
    "beacon":            1102,
}

ACTION_MESSAGES = {
    "auth_failure": [
        "Repeated failed logon for account '{user}' — {count} attempts in 60s",
        "Brute-force detected: {count} failed SSH auth from {source_country}",
        "Account lockout triggered after {count} failed logons against {host}",
    ],
    "scan": [
        "SYN scan detected: {count} ports probed from {source_country}",
        "Nmap-style probe on ports 22,80,443,3306,5432",
        "Horizontal scan: {source_country} swept /24 subnet on port 445",
    ],
    "anomaly": [
        "Unusual outbound data volume: {count} MB in 60s from {host}",
        "Rare parent-child process: explorer.exe → powershell.exe -enc … on {host}",
        "Memory anomaly: unsigned DLL injected into lsass.exe on {host}",
    ],
    "intrusion_attempt": [
        "Exploit attempt against CVE-2021-44228 (Log4Shell) from {source_country}",
        "SQL injection pattern in POST /api/login from {source_country}",
        "Shellshock payload in HTTP User-Agent from {source_country}",
    ],
    "policy_violation": [
        "Windows Firewall disabled on {host} by {process}",
        "AppLocker policy bypassed via regsvr32.exe on {host}",
        "UAC disabled via registry modification on {host}",
    ],
    "beacon": [
        "Cobalt Strike beacon C2 traffic from {host} → {source_country}",
        "Mimikatz credential dump activity on {host}",
        "Ransomware behavioural signature on {host}: mass file encryption",
    ],
    "lateral_movement": [
        "Pass-the-Hash login to {dest} from {host}",
        "Suspicious RDP session: {host} → {dest} outside business hours",
        "WMI remote execution: {host} spawned process on {dest}",
    ],
}

_SYSLOG_PRI = {"low": "<30>", "medium": "<28>", "high": "<11>", "critical": "<2>"}


def _walk(current: float, lo: float, hi: float, step: float) -> float:
    current += random.uniform(-step, step)
    return round(max(lo, min(hi, current)), 1)


def next_metrics() -> dict:
    global _cpu, _mem
    _cpu = _walk(_cpu, 5, 95, 3)
    _mem = _walk(_mem, 20, 92, 1.5)
    return {
        "cpu_percent":        round(_cpu + random.uniform(-1, 1), 1),
        "memory_percent":     round(_mem + random.uniform(-0.5, 0.5), 1),
        "disk_percent":       round(random.uniform(52, 58), 1),
        "network_in_mbps":    round(random.uniform(8, 240), 1),
        "network_out_mbps":   round(random.uniform(4, 120), 1),
        "active_connections": random.randint(60, 450),
        "alerts_last_hour":   random.randint(4, 95),
    }


def _format_log_original(action: str, severity: str, host: str, process: str | None,
                         message: str, module: str, ts: str) -> str:
    short_ts = ts[:19].replace("T", " ")
    proc = process or "-"

    if module == "winevent":
        evt_id = WIN_EVENT_IDS.get(action, 0)
        return (f"[{short_ts}] EventID={evt_id} Source=Microsoft-Windows-Security-Auditing "
                f"Hostname={host} Severity={severity.upper()} Process={proc} "
                f"Msg={message[:80]}")

    if module == "syslog":
        pri = _SYSLOG_PRI.get(severity, "<30>")
        return f"{pri}{short_ts} {host} {proc}: {message[:100]}"

    if module == "cef":
        sev_num = {"low": 2, "medium": 5, "high": 7, "critical": 10}.get(severity, 5)
        return (f"CEF:0|SOC-Dashboard|EventEngine|2.0|{action}|{action.replace('_', ' ').title()}"
                f"|{sev_num}|src={host} msg={message[:80]}")

    if module == "netflow":
        return f"netflow {short_ts} {host} bytes={random.randint(1000, 999999)} pkts={random.randint(10, 9999)}"

    return message


def maybe_event() -> dict | None:
    """Returns an ECS-shaped event dict, or None for this tick."""
    if random.random() > 0.20:
        return None

    # 30% of events come from "active attackers" doing brute-force / scanning,
    # which causes threshold-based detection rules to fire under demo load.
    is_attacker = random.random() < 0.30
    if is_attacker:
        action = random.choice(["auth_failure", "scan"])
    else:
        action = random.choice(list(ACTION_TEMPLATE.keys()))
    category, outcome, module = ACTION_TEMPLATE[action]
    tactic, t_id, t_name = ACTION_MITRE[action]

    severity = random.choices(
        ["low", "medium", "high", "critical"],
        weights=[0.30, 0.35, 0.25, 0.10],
    )[0]

    geo = random_source()
    host = random.choice(_HOSTNAMES)
    user = random.choice(_USERS) if action in {"auth_failure", "lateral_movement"} else None
    procs = _PROCESSES_BY_MODULE.get(module, [])
    process = random.choice(procs) if procs else None
    count = random.randint(1, 60)
    dest_ip = random.choice(_INTERNAL_IPS) if random.random() > 0.3 else None

    template = random.choice(ACTION_MESSAGES[action])
    message = template.format(
        count=count,
        source_country=geo["country"],
        host=host,
        dest=dest_ip or "-",
        user=user or "-",
        process=process or "-",
    )

    ts = datetime.now(timezone.utc).isoformat()
    event_id = f"evt-{random.randint(100_000, 999_999)}"
    # If this came from the attacker behaviour branch, use the attacker IP pool
    # so threshold rules (5 failed auth in 60s, 3 scans in 30s) actually fire.
    if is_attacker:
        src_ip = random.choice(_ATTACKER_IPS)
    else:
        src_ip = f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"

    log_original = _format_log_original(action, severity, host, process, message, module, ts)

    return make_event(
        event_id=event_id,
        timestamp=ts,
        category=category,
        action=action,
        outcome=outcome,
        severity=severity,
        module=module,
        message=message,
        source_ip=src_ip,
        source_country=geo["country"],
        source_lat=geo["lat"] + random.uniform(-2, 2),
        source_lon=geo["lng"] + random.uniform(-2, 2),
        destination_ip=dest_ip,
        host_name=host,
        user_name=user,
        process_name=process,
        tactic=tactic,
        technique_id=t_id,
        technique_name=t_name,
        log_original=log_original,
        extra={"matched_count": count},
    )


def get_topology() -> tuple[list[dict], list[dict]]:
    nodes = [
        {"id": "ext-1",    "label": "External",    "type": "external",    "risk": 0.92},
        {"id": "fw-1",     "label": "Firewall",    "type": "firewall",    "risk": 0.18},
        {"id": "sw-core",  "label": "Core Switch", "type": "switch",      "risk": 0.10},
        {"id": "sw-edge",  "label": "Edge Switch", "type": "switch",      "risk": 0.14},
        {"id": "srv-web",  "label": "Web Server",  "type": "server",      "risk": 0.58},
        {"id": "srv-db",   "label": "DB Server",   "type": "server",      "risk": 0.28},
        {"id": "srv-auth", "label": "Auth Server", "type": "server",      "risk": 0.42},
        {"id": "wks-1",    "label": "WKS-001",     "type": "workstation", "risk": 0.72},
        {"id": "wks-2",    "label": "WKS-002",     "type": "workstation", "risk": 0.21},
        {"id": "wks-3",    "label": "WKS-003",     "type": "workstation", "risk": 0.87},
        {"id": "wks-4",    "label": "WKS-004",     "type": "workstation", "risk": 0.15},
    ]
    edges = [
        {"source": "ext-1",   "target": "fw-1"},
        {"source": "fw-1",    "target": "sw-core"},
        {"source": "sw-core", "target": "sw-edge"},
        {"source": "sw-core", "target": "srv-web"},
        {"source": "sw-core", "target": "srv-db"},
        {"source": "sw-core", "target": "srv-auth"},
        {"source": "sw-edge", "target": "wks-1"},
        {"source": "sw-edge", "target": "wks-2"},
        {"source": "sw-edge", "target": "wks-3"},
        {"source": "sw-edge", "target": "wks-4"},
    ]
    return nodes, edges
