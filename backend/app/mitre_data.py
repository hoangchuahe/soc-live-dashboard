"""
Subset of MITRE ATT&CK Enterprise techniques mapped to the event types the simulator generates.
Full matrix: https://attack.mitre.org/
"""

TACTICS_ORDER = [
    "Reconnaissance",
    "Initial Access",
    "Execution",
    "Persistence",
    "Privilege Escalation",
    "Defense Evasion",
    "Credential Access",
    "Discovery",
    "Lateral Movement",
    "Collection",
    "Command and Control",
    "Exfiltration",
    "Impact",
]

# technique_id, name, tactic, event_types that map to it
TECHNIQUES: list[dict] = [
    {"id": "T1595",     "name": "Active Scanning",              "tactic": "Reconnaissance",       "events": ["PORT_SCAN"]},
    {"id": "T1190",     "name": "Exploit Public-Facing App",    "tactic": "Initial Access",       "events": ["INTRUSION_ATTEMPT"]},
    {"id": "T1078",     "name": "Valid Accounts",               "tactic": "Initial Access",       "events": ["AUTH_FAILURE"]},
    {"id": "T1059.001", "name": "PowerShell",                   "tactic": "Execution",            "events": ["ANOMALY", "MALWARE_DETECTED"]},
    {"id": "T1059.003", "name": "Windows Command Shell",        "tactic": "Execution",            "events": ["ANOMALY"]},
    {"id": "T1053.005", "name": "Scheduled Task",               "tactic": "Persistence",          "events": ["POLICY_VIOLATION"]},
    {"id": "T1547.001", "name": "Registry Run Keys",            "tactic": "Persistence",          "events": ["ANOMALY"]},
    {"id": "T1548.002", "name": "Bypass UAC",                   "tactic": "Privilege Escalation", "events": ["POLICY_VIOLATION", "INTRUSION_ATTEMPT"]},
    {"id": "T1055",     "name": "Process Injection",            "tactic": "Defense Evasion",      "events": ["MALWARE_DETECTED", "ANOMALY"]},
    {"id": "T1562.001", "name": "Disable Security Tools",       "tactic": "Defense Evasion",      "events": ["POLICY_VIOLATION"]},
    {"id": "T1003.001", "name": "LSASS Memory Dump",            "tactic": "Credential Access",    "events": ["MALWARE_DETECTED"]},
    {"id": "T1110.001", "name": "Password Guessing",            "tactic": "Credential Access",    "events": ["AUTH_FAILURE"]},
    {"id": "T1046",     "name": "Network Service Discovery",    "tactic": "Discovery",            "events": ["PORT_SCAN"]},
    {"id": "T1021.001", "name": "Remote Desktop Protocol",      "tactic": "Lateral Movement",     "events": ["LATERAL_MOVEMENT"]},
    {"id": "T1021.002", "name": "SMB / Windows Admin Shares",   "tactic": "Lateral Movement",     "events": ["LATERAL_MOVEMENT"]},
    {"id": "T1071.001", "name": "Web Protocols C2",             "tactic": "Command and Control",  "events": ["ANOMALY", "INTRUSION_ATTEMPT"]},
    {"id": "T1041",     "name": "Exfiltration Over C2 Channel", "tactic": "Exfiltration",         "events": ["ANOMALY"]},
    {"id": "T1486",     "name": "Data Encrypted for Impact",    "tactic": "Impact",               "events": ["MALWARE_DETECTED"]},
]

# Lookup: event_type → list of matching techniques
_BY_EVENT: dict[str, list[dict]] = {}
for t in TECHNIQUES:
    for ev in t["events"]:
        _BY_EVENT.setdefault(ev, []).append(t)


def technique_for(event_type: str) -> dict | None:
    import random
    candidates = _BY_EVENT.get(event_type, [])
    return random.choice(candidates) if candidates else None
