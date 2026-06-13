import { useEffect, useRef, useState } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { Header } from './components/Layout'
import { DashboardView } from './components/DashboardView'
import { SearchPanel } from './components/SearchPanel'
import { UiProvider } from './context/UiContext'
import { useUi } from './context/UiContext'
import { matchesProvenance } from './lib/provenance'
import type { Preset } from './lib/timeRange'
import { ecs } from './types'
import type { MetricPoint, NetworkNode, NetworkEdge, EcsEvent, Metrics, AttackArc } from './types'

const WS_URL = import.meta.env.DEV ? 'ws://localhost:8000/ws' : `ws://${window.location.host}/ws`
const MAX_HISTORY = 60
const MAX_ARCS = 30
const MAX_EVENTS = 200

export default function App() {
  return (
    <UiProvider>
      <AppInner />
    </UiProvider>
  )
}

function AppInner() {
  const { frame, status } = useWebSocket(WS_URL)
  const ui = useUi()
  const pausedRef = useRef(ui.livePaused)
  useEffect(() => { pausedRef.current = ui.livePaused }, [ui.livePaused])

  const [history, setHistory] = useState<MetricPoint[]>([])
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [events, setEvents]   = useState<EcsEvent[]>([])
  const [alerts, setAlerts]   = useState<EcsEvent[]>([])
  const [nodes, setNodes]     = useState<NetworkNode[]>([])
  const [edges, setEdges]     = useState<NetworkEdge[]>([])
  const [arcs, setArcs]       = useState<AttackArc[]>([])
  const [pivot, setPivot] = useState<{ open: boolean; query: string; preset: Preset }>({ open: false, query: '', preset: '15m' })

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const q = params.get('q')
    const raw = params.get('preset')
    const valid = new Set(['5m', '15m', '1h', '24h'])
    const p: Preset = raw && valid.has(raw) ? (raw as Preset) : '15m'
    if (q) setPivot({ open: true, query: q, preset: p })
  }, [])

  useEffect(() => {
    fetch('/api/topology').then(r => r.json()).then(d => { setNodes(d.nodes); setEdges(d.edges) }).catch(() => {})
  }, [])

  useEffect(() => {
    fetch('/api/events').then(r => r.json()).then(d => {
      const evts: EcsEvent[] = d.events ?? []
      setEvents(evts)
      setArcs(evts.filter(e => ecs.lat(e) || ecs.lon(e)).slice(-MAX_ARCS).map(e => ({
        id: e.event.id, country: ecs.country(e), lat: ecs.lat(e), lng: ecs.lon(e),
        severity: ecs.severity(e), count: ecs.count(e), provenance: ecs.provenance(e),
      })))
    }).catch(() => {})
    fetch('/api/alerts').then(r => r.json()).then(d => setAlerts(d.alerts ?? [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (!frame || pausedRef.current) return
    setMetrics(frame.metrics)
    setHistory(prev => {
      const pt: MetricPoint = { tick: frame.tick, cpu: frame.metrics.cpu_percent, memory: frame.metrics.memory_percent, networkIn: frame.metrics.network_in_mbps, networkOut: frame.metrics.network_out_mbps }
      const next = [...prev, pt]
      return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next
    })
    if (frame.event) {
      const e = frame.event
      setEvents(prev => { const next = [...prev, e]; return next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next })
      const lat = ecs.lat(e), lon = ecs.lon(e)
      if (lat || lon) {
        setArcs(prev => {
          const next: AttackArc[] = [...prev, { id: e.event.id, country: ecs.country(e), lat, lng: lon, severity: ecs.severity(e), count: ecs.count(e), provenance: ecs.provenance(e) }]
          return next.length > MAX_ARCS ? next.slice(-MAX_ARCS) : next
        })
      }
    }
    if (frame.alerts && frame.alerts.length > 0) {
      setAlerts(prev => { const next = [...prev, ...frame.alerts]; return next.length > 100 ? next.slice(-100) : next })
    }
  }, [frame])

  const fEvents = events.filter(e => matchesProvenance(e, ui.provenance))
  const fAlerts = alerts.filter(e => matchesProvenance(e, ui.provenance))
  const fArcs = arcs.filter(a => ui.provenance === 'all' || (a.provenance ?? 'live') === ui.provenance)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col">
      <Header status={status} />
      <DashboardView
        metrics={metrics} history={history} events={fEvents} alerts={fAlerts}
        arcs={fArcs} nodes={nodes} edges={edges}
        onPivot={(query) => setPivot({ open: true, query, preset: '15m' })}
      />
      <SearchPanel
        open={pivot.open} initialQuery={pivot.query} initialPreset={pivot.preset}
        onClose={() => setPivot(s => ({ ...s, open: false }))}
      />
    </div>
  )
}
