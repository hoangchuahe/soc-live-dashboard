from pydantic import BaseModel
from typing import Optional


class SecurityEvent(BaseModel):
    id: str
    timestamp: str
    type: str
    severity: str
    source_ip: str
    source_country: str
    source_lat: float
    source_lng: float
    destination_ip: Optional[str] = None
    message: str
    count: int
    # MITRE ATT&CK
    technique_id: Optional[str] = None
    technique_name: Optional[str] = None
    tactic: Optional[str] = None
    # Host context
    hostname: Optional[str] = None
    process: Optional[str] = None
    event_id: Optional[int] = None      # Windows Event ID or syslog priority
    log_format: str = "winevent"        # winevent | syslog | netflow | cef
    raw_log: Optional[str] = None       # formatted log line as it would appear in SIEM


class NetworkNode(BaseModel):
    id: str
    label: str
    type: str  # firewall | switch | server | workstation | external
    risk: float


class NetworkEdge(BaseModel):
    source: str
    target: str
