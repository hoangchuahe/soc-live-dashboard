"""
Realistic SOC event simulator.
Event types, Windows Event IDs, MITRE ATT&CK mappings, and geo attribution
are modelled after real-world threat intelligence patterns.
"""

import random
from datetime import datetime, timezone
from .models import SecurityEvent, NetworkNode, NetworkEdge
from .geo_data import random_source
from .mitre_data import technique_for

_cpu = 45.0
_mem = 62.0

# ── Realistic host inventory ──────────────────────────────────────────────────
_HOSTNAMES = [
    "DC01.corp.local", "WEB-PROD-01", "DB-MYSQL-02", "AUTH-SRV-01",
    "WKS-HOANG-01", "WKS-ALICE-02", "WKS-BOB-03", "JUMP-SRV-01",
    "BACKUP-SRV-01", "MON-ELK-01",
]

_PROCESSES = {
    "winevent": ["lsass.exe", "powershell.exe", "cmd.exe", "svchost.exe",
                 "explorer.exe", "rundll32.exe", "mshta.exe", "wscript.exe"],
    "syslog":   ["/usr/sbin/sshd", "/bin/bash", "sudo", "cron", "nginx",
                 "python3", "systemd"],
    "cef":      ["AV-Engine", "IDS-Snort", "Firewall-FW01", "WAF-ModSec"],
}

# Windows Event IDs commonly seen in SOC alerts
_WIN_EVENT_IDS = {
    "AUTH_FAILURE":       4625,   # An account failed to log on
    "LATERAL_MOVEMENT":   4648,   # Logon using explicit credentials
    "POLICY_VIOLATION":   4719,   # System audit policy was changed
    "ANOMALY":            4688,   # A new process has been created
    "MALWARE_DETECTED":   1102,   # The audit log was cleared (indicator)
    "INTRUSION_ATTEMPT":  4625,
    "PORT_SCAN":          None,   # Network-layer, no WinEvent
}

_SYSLOG_PRIORITIES = {
    "critical": "<2>",   # kern.crit
    "high":     "<11>",  # daemon.err
    "medium":   "<28>",  # daemon.warning
    "low":      "<30>",  # daemon.info
}

_INTERNAL = [f"192.168.{s}.{h}" for s in (1, 2, 10) for h in range(10, 50)]

# Map event type → descriptive messages
_MESSAGES: dict[str, list[str]] = {
    "AUTH_FAILURE": [
        "Repeated failed logon for account 'administrator' — {count} attempts in 60s",
        "Brute-force detected: {count} failed SSH auth from {src}",
        "Account lockout triggered after {count} failed logons",
    ],
    "PORT_SCAN": [
        "SYN scan detected across {count} ports from {src}",
        "Nmap-style probe on ports 22,80,443,3306,5432 from {src}",
        "Horizontal scan: {src} swept /24 subnet on port 445",
    ],
    "ANOMALY": [
        "Unusual outbound data volume: {count} MB in 60s from {host}",
        "Rare parent-child process: explorer.exe → powershell.exe -enc ... on {host}",
        "Memory anomaly: unsigned DLL injected into lsass.exe",
    ],
    "INTRUSION_ATTEMPT": [
        "Exploit attempt against CVE-2021-44228 (Log4Shell) from {src}",
        "SQL injection pattern in POST /api/login from {src}",
        "Shellshock payload in HTTP User-Agent from {src}",
    ],
    "POLICY_VIOLATION": [
        "Windows Firewall disabled on {host} by {proc}",
        "AppLocker policy bypassed via regsvr32.exe on {host}",
        "UAC disabled via registry key modification on {host}",
    ],
    "MALWARE_DETECTED": [
        "Ransomware behavioural signature matched on {host}: mass file encryption",
        "Cobalt Strike beacon C2 traffic detected from {host} → {src}",
        "Mimikatz credential dump activity on {host}",
    ],
    "LATERAL_MOVEMENT": [
        "Pass-the-Hash login to {dest} from {host}",
        "Suspicious RDP session: {host} → {dest} outside business hours",
        "WMI remote execution: {host} spawned process on {dest}",
    ],
}


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


def _format_raw_log(
    event_type: str,
    severity: str,
    hostname: str,
    process: str,
    message: str,
    event_id: int | None,
    log_format: str,
    ts: str,
) -> str:
    short_ts = ts[:19].replace("T", " ")
    if log_format == "winevent":
        return (
            f"[{short_ts}] EventID={event_id} Source=Microsoft-Windows-Security-Auditing "
            f"Hostname={hostname} Severity={severity.upper()} "
            f"Process={process} Msg={message[:80]}"
        )
    if log_format == "syslog":
        pri = _SYSLOG_PRIORITIES.get(severity, "<30>")
        return f"{pri}{short_ts} {hostname} {process}: {message[:100]}"
    if log_format == "cef":
        sev_num = {"low": 2, "medium": 5, "high": 7, "critical": 10}.get(severity, 5)
        return (
            f"CEF:0|SOC-Dashboard|EventEngine|1.0|{event_type}|{event_type.replace('_', ' ').title()}"
            f"|{sev_num}|src={hostname} msg={message[:80]}"
        )
    return message


def maybe_event() -> SecurityEvent | None:
    if random.random() > 0.20:
        return None

    event_type = random.choice(list(_MESSAGES.keys()))
    severity = random.choices(
        ["low", "medium", "high", "critical"],
        weights=[0.30, 0.35, 0.25, 0.10],
    )[0]

    geo = random_source()
    technique = technique_for(event_type)
    hostname = random.choice(_HOSTNAMES)
    count = random.randint(1, 60)
    dest = random.choice(_INTERNAL)

    # Pick log format based on event type
    log_format = (
        "netflow" if event_type == "PORT_SCAN"
        else "cef"  if event_type == "MALWARE_DETECTED"
        else "syslog" if random.random() < 0.3
        else "winevent"
    )

    proc_list = _PROCESSES.get(log_format if log_format != "netflow" else "winevent", _PROCESSES["winevent"])
    process = random.choice(proc_list)
    event_id = _WIN_EVENT_IDS.get(event_type)

    template = random.choice(_MESSAGES[event_type])
    message = template.format(
        count=count,
        src=geo["country"],
        host=hostname,
        dest=dest,
        proc=process,
    )

    ts = datetime.now(timezone.utc).isoformat()

    return SecurityEvent(
        id=f"evt-{random.randint(100_000, 999_999)}",
        timestamp=ts,
        type=event_type,
        severity=severity,
        source_ip=f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
        source_country=geo["country"],
        source_lat=geo["lat"] + random.uniform(-2, 2),
        source_lng=geo["lng"] + random.uniform(-2, 2),
        destination_ip=dest if random.random() > 0.3 else None,
        message=message,
        count=count,
        technique_id=technique["id"] if technique else None,
        technique_name=technique["name"] if technique else None,
        tactic=technique["tactic"] if technique else None,
        hostname=hostname,
        process=process,
        event_id=event_id,
        log_format=log_format,
        raw_log=_format_raw_log(event_type, severity, hostname, process, message, event_id, log_format, ts),
    )


def get_topology() -> tuple[list[NetworkNode], list[NetworkEdge]]:
    nodes = [
        NetworkNode(id="ext-1",    label="External",    type="external",    risk=0.92),
        NetworkNode(id="fw-1",     label="Firewall",    type="firewall",    risk=0.18),
        NetworkNode(id="sw-core",  label="Core Switch", type="switch",      risk=0.10),
        NetworkNode(id="sw-edge",  label="Edge Switch", type="switch",      risk=0.14),
        NetworkNode(id="srv-web",  label="Web Server",  type="server",      risk=0.58),
        NetworkNode(id="srv-db",   label="DB Server",   type="server",      risk=0.28),
        NetworkNode(id="srv-auth", label="Auth Server", type="server",      risk=0.42),
        NetworkNode(id="wks-1",    label="WKS-001",     type="workstation", risk=0.72),
        NetworkNode(id="wks-2",    label="WKS-002",     type="workstation", risk=0.21),
        NetworkNode(id="wks-3",    label="WKS-003",     type="workstation", risk=0.87),
        NetworkNode(id="wks-4",    label="WKS-004",     type="workstation", risk=0.15),
    ]
    edges = [
        NetworkEdge(source="ext-1",   target="fw-1"),
        NetworkEdge(source="fw-1",    target="sw-core"),
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
