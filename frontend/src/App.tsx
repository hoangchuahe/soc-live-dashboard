import { useEffect, useState } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { Header, Panel } from './components/Layout'
import { StatsCard } from './components/StatsCard'
import { MetricsChart } from './components/MetricsChart'
import { NetworkGraph } from './components/NetworkGraph'
import { EventTimeline } from './components/EventTimeline'
import { AlertFeed } from './components/AlertFeed'
import { GeoMap } from './components/GeoMap'
import { MitrePanel, useMitreTactics } from './components/MitrePanel'
import { CveFeed, useCves } from './components/CveFeed'
import { LogViewer } from './components/LogViewer'
import type { MetricPoint, NetworkNode, NetworkEdge, SecurityEvent, Metrics, AttackArc } from './types'

const WS_URL = import.meta.env.DEV
  ? 'ws://localhost:8000/ws'
  : `ws://${window.location.host}/ws`

const MAX_HISTORY = 60
const MAX_ARCS = 30

export default function App() {
  const { frame, status } = useWebSocket(WS_URL)

  const [history, setHistory]   = useState<MetricPoint[]>([])
  const [metrics, setMetrics]   = useState<Metrics | null>(null)
  const [events, setEvents]     = useState<SecurityEvent[]>([])
  const [nodes, setNodes]       = useState<NetworkNode[]>([])
  const [edges, setEdges]       = useState<NetworkEdge[]>([])
  const [arcs, setArcs]         = useState<AttackArc[]>([])
  const [activeTab, setActiveTab] = useState<'timeline' | 'logs'>('timeline')

  const tactics      = useMitreTactics()
  const { cves, loading: cvesLoading } = useCves()

  // One-time data loads
  useEffect(() => {
    fetch('/api/topology')
      .then(r => r.json())
      .then(d => { setNodes(d.nodes); setEdges(d.edges) })
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetch('/api/events')
      .then(r => r.json())
      .then(d => {
        const evts: SecurityEvent[] = d.events ?? []
        setEvents(evts)
        const initial = evts
          .filter(e => e.source_lat && e.source_lng)
          .slice(-MAX_ARCS)
          .map(e => ({
            id: e.id,
            country: e.source_country,
            lat: e.source_lat,
            lng: e.source_lng,
            severity: e.severity,
            count: e.count,
          }))
        setArcs(initial)
      })
      .catch(() => {})
  }, [])

  // Live frame processing
  useEffect(() => {
    if (!frame) return

    setMetrics(frame.metrics)

    setHistory(prev => {
      const pt: MetricPoint = {
        tick: frame.tick,
        cpu: frame.metrics.cpu_percent,
        memory: frame.metrics.memory_percent,
        networkIn: frame.metrics.network_in_mbps,
        networkOut: frame.metrics.network_out_mbps,
      }
      const next = [...prev, pt]
      return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next
    })

    if (frame.event) {
      const e = frame.event
      setEvents(prev => {
        const next = [...prev, e]
        return next.length > 200 ? next.slice(-200) : next
      })
      if (e.source_lat && e.source_lng) {
        setArcs(prev => {
          const next: AttackArc[] = [
            ...prev,
            { id: e.id, country: e.source_country, lat: e.source_lat, lng: e.source_lng, severity: e.severity, count: e.count },
          ]
          return next.length > MAX_ARCS ? next.slice(-MAX_ARCS) : next
        })
      }
    }
  }, [frame])

  const cpu = metrics?.cpu_percent ?? 0
  const mem = metrics?.memory_percent ?? 0
  const criticals = events.filter(e => e.severity === 'critical').length

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col">
      <Header status={status} />

      <main className="flex-1 p-3 flex flex-col gap-3">

        {/* ── Row 1: Stats ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
          <StatsCard label="CPU"          value={cpu.toFixed(1)}                           unit="%" color="cyan"   danger={cpu > 85} />
          <StatsCard label="Memory"       value={mem.toFixed(1)}                           unit="%" color="purple" danger={mem > 85} />
          <StatsCard label="Disk"         value={metrics?.disk_percent.toFixed(1) ?? '—'}  unit="%" color="orange" />
          <StatsCard label="Net In"       value={metrics?.network_in_mbps.toFixed(0) ?? '—'} unit="Mbps" color="green" />
          <StatsCard label="Net Out"      value={metrics?.network_out_mbps.toFixed(0) ?? '—'} unit="Mbps" color="green" />
          <StatsCard label="Connections"  value={metrics?.active_connections ?? '—'}       color="cyan" />
          <StatsCard label="Alerts / hr"  value={metrics?.alerts_last_hour ?? '—'}         color="red" danger={criticals > 0} />
        </div>

        {/* ── Row 2: Geo map + Network topology ── */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-3" style={{ minHeight: 280 }}>
          <Panel title={`Attack Origin Map  (${arcs.length} arcs)`} className="lg:col-span-3">
            <GeoMap arcs={arcs} />
          </Panel>
          <Panel title="Network Topology" className="lg:col-span-2">
            <NetworkGraph nodes={nodes} edges={edges} />
          </Panel>
        </div>

        {/* ── Row 3: Metrics + CVE feed ── */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-3" style={{ minHeight: 240 }}>
          <Panel title="System Metrics — Live (60 s)" className="lg:col-span-3">
            <div className="p-2 h-full">
              <MetricsChart data={history} />
            </div>
          </Panel>
          <Panel title="CVE Intel Feed  · NVD" className="lg:col-span-2">
            <CveFeed cves={cves} loading={cvesLoading} />
          </Panel>
        </div>

        {/* ── Row 4: Timeline/Logs + MITRE + Alerts ── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3" style={{ minHeight: 220 }}>

          {/* Timeline / Log viewer — tabbed */}
          <div className="lg:col-span-5 relative scanline bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col overflow-hidden">
            <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
                <div className="flex gap-1">
                  {(['timeline', 'logs'] as const).map(tab => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`text-xs px-3 py-1 rounded transition-colors ${
                        activeTab === tab
                          ? 'bg-cyan-500/20 text-cyan-400'
                          : 'text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      {tab === 'timeline' ? 'Event Timeline' : 'Raw Logs'}
                    </button>
                  ))}
                </div>
              </div>
              <span className="text-[10px] text-slate-600">{events.length} events</span>
            </div>
            <div className="flex-1 overflow-hidden">
              {activeTab === 'timeline'
                ? <div className="p-2 h-full"><EventTimeline events={events.slice(-40)} /></div>
                : <LogViewer events={events.slice(-50)} />
              }
            </div>
          </div>

          {/* MITRE ATT&CK heatmap */}
          <Panel title="MITRE ATT&CK" className="lg:col-span-3">
            <MitrePanel tactics={tactics} />
          </Panel>

          {/* Alert feed */}
          <Panel title={`Alert Feed  (${criticals} critical)`} className="lg:col-span-4">
            <AlertFeed events={events.slice(-40)} />
          </Panel>

        </div>

      </main>
    </div>
  )
}
