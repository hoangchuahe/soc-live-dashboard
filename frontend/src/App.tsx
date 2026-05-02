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
import { RiskPanel, useRiskTop } from './components/RiskPanel'
import { RulesPanel, useRules } from './components/RulesPanel'
import { ecs } from './types'
import type { MetricPoint, NetworkNode, NetworkEdge, EcsEvent, Metrics, AttackArc } from './types'

const WS_URL = import.meta.env.DEV
  ? 'ws://localhost:8000/ws'
  : `ws://${window.location.host}/ws`

const MAX_HISTORY = 60
const MAX_ARCS = 30
const MAX_EVENTS = 200

export default function App() {
  const { frame, status } = useWebSocket(WS_URL)

  const [history, setHistory]   = useState<MetricPoint[]>([])
  const [metrics, setMetrics]   = useState<Metrics | null>(null)
  const [events, setEvents]     = useState<EcsEvent[]>([])
  const [alerts, setAlerts]     = useState<EcsEvent[]>([])
  const [nodes, setNodes]       = useState<NetworkNode[]>([])
  const [edges, setEdges]       = useState<NetworkEdge[]>([])
  const [arcs, setArcs]         = useState<AttackArc[]>([])
  const [activeTab, setActiveTab] = useState<'timeline' | 'logs'>('timeline')
  const [activeBottomTab, setActiveBottomTab] = useState<'risk' | 'rules'>('risk')

  const tactics                          = useMitreTactics()
  const { cves, loading: cvesLoading }   = useCves()
  const riskEntities                     = useRiskTop()
  const rules                            = useRules()

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
        const evts: EcsEvent[] = d.events ?? []
        setEvents(evts)
        const initial: AttackArc[] = evts
          .filter(e => ecs.lat(e) || ecs.lon(e))
          .slice(-MAX_ARCS)
          .map(e => ({
            id: e.event.id,
            country: ecs.country(e),
            lat: ecs.lat(e),
            lng: ecs.lon(e),
            severity: ecs.severity(e),
            count: ecs.count(e),
          }))
        setArcs(initial)
      })
      .catch(() => {})

    fetch('/api/alerts')
      .then(r => r.json())
      .then(d => setAlerts(d.alerts ?? []))
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
        return next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next
      })
      const lat = ecs.lat(e)
      const lon = ecs.lon(e)
      if (lat || lon) {
        setArcs(prev => {
          const next: AttackArc[] = [
            ...prev,
            { id: e.event.id, country: ecs.country(e), lat, lng: lon, severity: ecs.severity(e), count: ecs.count(e) },
          ]
          return next.length > MAX_ARCS ? next.slice(-MAX_ARCS) : next
        })
      }
    }

    if (frame.alerts && frame.alerts.length > 0) {
      setAlerts(prev => {
        const next = [...prev, ...frame.alerts]
        return next.length > 100 ? next.slice(-100) : next
      })
    }
  }, [frame])

  const cpu = metrics?.cpu_percent ?? 0
  const mem = metrics?.memory_percent ?? 0
  const criticalEvents = events.filter(e => ecs.severity(e) === 'critical').length

  // Combined event stream for timeline (events + alerts, sorted by time)
  const combined: EcsEvent[] = [...events, ...alerts]
    .sort((a, b) => a['@timestamp'].localeCompare(b['@timestamp']))
    .slice(-50)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col">
      <Header status={status} />

      <main className="flex-1 p-3 flex flex-col gap-3">

        {/* ── Row 1: Stats ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
          <StatsCard label="CPU"          value={cpu.toFixed(1)}                             unit="%"    color="cyan"   danger={cpu > 85} />
          <StatsCard label="Memory"       value={mem.toFixed(1)}                             unit="%"    color="purple" danger={mem > 85} />
          <StatsCard label="Disk"         value={metrics?.disk_percent.toFixed(1) ?? '—'}    unit="%"    color="orange" />
          <StatsCard label="Net In"       value={metrics?.network_in_mbps.toFixed(0) ?? '—'} unit="Mbps" color="green" />
          <StatsCard label="Net Out"      value={metrics?.network_out_mbps.toFixed(0) ?? '—'} unit="Mbps" color="green" />
          <StatsCard label="Detections"   value={alerts.length}                              color="red"  danger={alerts.length > 0} />
          <StatsCard label="Alerts / hr"  value={metrics?.alerts_last_hour ?? '—'}           color="red"  danger={criticalEvents > 0} />
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

        {/* ── Row 4: Timeline/Logs + MITRE + Risk/Rules ── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3" style={{ minHeight: 260 }}>

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
              <span className="text-[10px] text-slate-600">
                {events.length} events · {alerts.length} alerts
              </span>
            </div>
            <div className="flex-1 overflow-hidden">
              {activeTab === 'timeline'
                ? <div className="p-2 h-full"><EventTimeline events={combined} /></div>
                : <LogViewer events={events.slice(-50)} />
              }
            </div>
          </div>

          {/* MITRE ATT&CK heatmap */}
          <Panel title="MITRE ATT&CK" className="lg:col-span-3">
            <MitrePanel tactics={tactics} />
          </Panel>

          {/* Risk-Based Alerting / Detection Rules — tabbed */}
          <div className="lg:col-span-4 relative scanline bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col overflow-hidden">
            <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
                <div className="flex gap-1">
                  {(['risk', 'rules'] as const).map(tab => (
                    <button
                      key={tab}
                      onClick={() => setActiveBottomTab(tab)}
                      className={`text-xs px-3 py-1 rounded transition-colors ${
                        activeBottomTab === tab
                          ? 'bg-cyan-500/20 text-cyan-400'
                          : 'text-slate-500 hover:text-slate-300'
                      }`}
                    >
                      {tab === 'risk' ? 'Top Risk Entities' : `Rules (${rules.length})`}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex-1 overflow-hidden">
              {activeBottomTab === 'risk'
                ? <RiskPanel entities={riskEntities} />
                : <RulesPanel rules={rules} />
              }
            </div>
          </div>

        </div>

        {/* ── Row 5: Alert Feed (full width) ── */}
        <div className="grid grid-cols-1 gap-3" style={{ minHeight: 200 }}>
          <Panel title={`Live Alert Feed  ·  ${criticalEvents} critical / ${alerts.length} rule-driven`}>
            <AlertFeed events={[...events, ...alerts].slice(-60)} />
          </Panel>
        </div>

      </main>
    </div>
  )
}
