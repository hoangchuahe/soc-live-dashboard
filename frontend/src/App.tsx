import { useEffect, useState } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { Header, Panel } from './components/Layout'
import { StatsCard } from './components/StatsCard'
import { MetricsChart } from './components/MetricsChart'
import { NetworkGraph } from './components/NetworkGraph'
import { EventTimeline } from './components/EventTimeline'
import { AlertFeed } from './components/AlertFeed'
import type { MetricPoint, NetworkNode, NetworkEdge, SecurityEvent, Metrics } from './types'

const WS_URL = import.meta.env.DEV
  ? 'ws://localhost:8000/ws'
  : `ws://${window.location.host}/ws`

const MAX_HISTORY = 60

export default function App() {
  const { frame, status } = useWebSocket(WS_URL)

  const [history, setHistory] = useState<MetricPoint[]>([])
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [events, setEvents] = useState<SecurityEvent[]>([])
  const [nodes, setNodes] = useState<NetworkNode[]>([])
  const [edges, setEdges] = useState<NetworkEdge[]>([])

  // Load topology once
  useEffect(() => {
    fetch('/api/topology')
      .then(r => r.json())
      .then(data => {
        setNodes(data.nodes)
        setEdges(data.edges)
      })
      .catch(() => {}) // backend may not be running in preview
  }, [])

  // Load existing events once
  useEffect(() => {
    fetch('/api/events')
      .then(r => r.json())
      .then(data => setEvents(data.events ?? []))
      .catch(() => {})
  }, [])

  // Process incoming frames
  useEffect(() => {
    if (!frame) return

    setMetrics(frame.metrics)

    setHistory(prev => {
      const point: MetricPoint = {
        tick: frame.tick,
        cpu: frame.metrics.cpu_percent,
        memory: frame.metrics.memory_percent,
        networkIn: frame.metrics.network_in_mbps,
        networkOut: frame.metrics.network_out_mbps,
      }
      const next = [...prev, point]
      return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next
    })

    if (frame.event) {
      setEvents(prev => {
        const next = [...prev, frame.event!]
        return next.length > 100 ? next.slice(-100) : next
      })
    }
  }, [frame])

  const cpu = metrics?.cpu_percent ?? 0
  const mem = metrics?.memory_percent ?? 0
  const criticalEvents = events.filter(e => e.severity === 'critical').length

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col">
      <Header status={status} />

      <main className="flex-1 p-4 grid gap-4" style={{ gridTemplateRows: 'auto 1fr 1fr' }}>

        {/* Stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          <StatsCard label="CPU" value={cpu.toFixed(1)} unit="%" color="cyan" danger={cpu > 85} />
          <StatsCard label="Memory" value={mem.toFixed(1)} unit="%" color="purple" danger={mem > 85} />
          <StatsCard label="Disk" value={metrics?.disk_percent.toFixed(1) ?? '—'} unit="%" color="orange" />
          <StatsCard label="Net In" value={metrics?.network_in_mbps.toFixed(0) ?? '—'} unit="Mbps" color="green" />
          <StatsCard label="Net Out" value={metrics?.network_out_mbps.toFixed(0) ?? '—'} unit="Mbps" color="green" />
          <StatsCard label="Connections" value={metrics?.active_connections ?? '—'} color="cyan" />
          <StatsCard label="Alerts / hr" value={metrics?.alerts_last_hour ?? '—'} color="red" danger={criticalEvents > 0} />
        </div>

        {/* Middle row: metrics chart + network graph */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <Panel title="System Metrics — Live (60s)" className="lg:col-span-3 min-h-[240px]">
            <div className="p-2 h-full">
              <MetricsChart data={history} />
            </div>
          </Panel>

          <Panel title="Network Topology" className="lg:col-span-2 min-h-[240px]">
            <NetworkGraph nodes={nodes} edges={edges} />
          </Panel>
        </div>

        {/* Bottom row: event timeline + alert feed */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <Panel title="Event Timeline" className="lg:col-span-3 min-h-[180px]">
            <div className="p-2 h-full">
              <EventTimeline events={events.slice(-40)} />
            </div>
          </Panel>

          <Panel title={`Alert Feed  (${events.length})`} className="lg:col-span-2 min-h-[180px]">
            <AlertFeed events={events.slice(-30)} />
          </Panel>
        </div>
      </main>
    </div>
  )
}
