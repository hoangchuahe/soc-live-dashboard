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
  destination_ip: string | null
  message: string
  count: number
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
