// ─── Elastic Common Schema (ECS) shape ──────────────────────────────────────
// The backend emits events conforming to ECS:
//   https://www.elastic.co/guide/en/ecs/current/

export interface EcsEvent {
  '@timestamp': string
  event: {
    id: string
    kind: 'event' | 'alert'
    category: string           // authentication | network | malware | configuration | intrusion_detection | detection
    action?: string
    outcome?: 'success' | 'failure' | 'unknown'
    severity: 'low' | 'medium' | 'high' | 'critical'
    module?: string            // winevent | syslog | netflow | cef
    dataset?: string           // windows.security | host.network | host.process | host.metrics | simulator.attack
  }
  source?: {
    ip?: string
    geo?: {
      country_name?: string
      location?: { lat: number; lon: number }
    }
  }
  destination?: { ip?: string }
  host?: { name?: string }
  user?: { name?: string }
  process?: { name?: string }
  threat?: {
    tactic?:    { name?: string } | null
    technique?: { id?: string; name?: string } | null
  }
  rule?: { id: string; name: string }       // populated only on alerts
  log?: { original?: string; level?: string }
  message: string
  labels?: { provenance?: 'live' | 'simulated' }
  matched_count?: number
  entity?: string
  triggering_event_id?: string
}

export interface MetricPoint {
  tick: number
  cpu: number
  memory: number
  networkIn: number
  networkOut: number
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
  event: EcsEvent | null
  alerts: EcsEvent[]
}

export interface HealthStatus {
  mode: 'demo' | 'live' | 'blend'
  sources: { name: string; available: boolean; detail: string }[]
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
  provenance?: 'live' | 'simulated'
}

export interface RiskEntity {
  name: string
  score: number
  rule_count: number
  last_updated_seconds_ago: number
}

export interface RuleSummary {
  id: string
  title: string
  severity: string
  tactic: string | null
  technique_id: string | null
  fire_count: number
  last_fired: string | null
  has_threshold: boolean
}

// ─── Helpers to extract flat fields from ECS events ──────────────────────────

export const ecs = {
  severity: (e: EcsEvent) => e.event.severity,
  type:     (e: EcsEvent) => e.event.action ?? e.event.category,
  source:   (e: EcsEvent) => e.source?.ip ?? '—',
  country:  (e: EcsEvent) => e.source?.geo?.country_name ?? 'Unknown',
  lat:      (e: EcsEvent) => e.source?.geo?.location?.lat ?? 0,
  lon:      (e: EcsEvent) => e.source?.geo?.location?.lon ?? 0,
  dest:     (e: EcsEvent) => e.destination?.ip ?? null,
  host:     (e: EcsEvent) => e.host?.name ?? null,
  tactic:   (e: EcsEvent) => e.threat?.tactic?.name ?? null,
  technique:(e: EcsEvent) => e.threat?.technique?.id ?? null,
  rawLog:   (e: EcsEvent) => e.log?.original ?? null,
  format:   (e: EcsEvent) => e.event.module ?? 'unknown',
  count:    (e: EcsEvent) => e.matched_count ?? 1,
  isAlert:  (e: EcsEvent) => e.event.kind === 'alert',
  provenance: (e: EcsEvent): 'live' | 'simulated' =>
    e.labels?.provenance === 'simulated' ? 'simulated' : 'live',
  isSimulated: (e: EcsEvent) => e.labels?.provenance === 'simulated',
  dataset:    (e: EcsEvent) => e.event.dataset ?? null,
}
