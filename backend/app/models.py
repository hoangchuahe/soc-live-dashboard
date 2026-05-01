from pydantic import BaseModel
from typing import Optional


class SecurityEvent(BaseModel):
    id: str
    timestamp: str
    type: str
    severity: str
    source_ip: str
    destination_ip: Optional[str]
    message: str
    count: int


class NetworkNode(BaseModel):
    id: str
    label: str
    type: str  # firewall | switch | server | workstation | external
    risk: float  # 0.0 – 1.0


class NetworkEdge(BaseModel):
    source: str
    target: str
