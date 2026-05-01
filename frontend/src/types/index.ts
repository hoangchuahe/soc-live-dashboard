export interface MetricPoint {
  tick: number
  cpu: number
  memory: number
  networkIn: number
  networkOut: number
}

export interface SecurityEvent {
  id: string
  timestamp: string
  type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  source_ip: string
  source_country: string
  source_lat: number
  source_lng: number
  destination_ip: string | null
  message: string
  count: number
  // MITRE ATT&CK
  technique_id: string | null
  technique_name: string | null
  tactic: string | null
  // Host context
  hostname: string | null
  process: string | null
  event_id: number | null
  log_format: 'winevent' | 'syslog' | 'netflow' | 'cef'
  raw_log: string | null
}

export interface NetworkNode {
  id: string
  label: string
  type: 'firewall' | 'switch' | 'server' | 'workstation' | 'external'
  risk: number
}

export interface NetworkEdge {
  source: string
  target: string
}

export interface Metrics {
  cpu_percent: number
  memory_percent: number
  disk_percent: number
  network_in_mbps: number
  network_out_mbps: number
  active_connections: number
  alerts_last_hour: number
}

export interface WsFrame {
  tick: number
  metrics: Metrics
  event: SecurityEvent | null
}

export interface CveItem {
  id: string
  description: string
  cvss: number | null
  cvss_vector: string | null
  published: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'unknown'
}

export interface MitreTactic {
  name: string
  count: number
}

export interface AttackArc {
  id: string
  country: string
  lat: number
  lng: number
  severity: string
  count: number
}
