import { useState } from 'react'
import { Panel } from './Layout'
import { StatsCard } from './StatsCard'
import { MetricsChart } from './MetricsChart'
import { NetworkGraph } from './NetworkGraph'
import { EventTimeline } from './EventTimeline'
import { AlertFeed } from './AlertFeed'
import { GeoMap } from './GeoMap'
import { MitrePanel, useMitreTactics } from './MitrePanel'
import { CveFeed, useCves } from './CveFeed'
import { LogViewer } from './LogViewer'
import { RiskPanel, useRiskTop } from './RiskPanel'
import { RulesPanel, useRules } from './RulesPanel'
import { ecs } from '../types'
import type { MetricPoint, NetworkNode, NetworkEdge, EcsEvent, Metrics, AttackArc } from '../types'

interface Props {
  metrics: Metrics | null
  history: MetricPoint[]
  events: EcsEvent[]
  alerts: EcsEvent[]
  arcs: AttackArc[]
  nodes: NetworkNode[]
  edges: NetworkEdge[]
  onPivot: (query: string) => void
}

export function DashboardView({ metrics, history, events, alerts, arcs, nodes, edges, onPivot }: Props) {
  const [activeTab, setActiveTab] = useState<'timeline' | 'logs'>('timeline')
  const [activeBottomTab, setActiveBottomTab] = useState<'risk' | 'rules'>('risk')

  const tactics = useMitreTactics()
  const { cves, loading: cvesLoading } = useCves()
  const riskEntities = useRiskTop()
  const rules = useRules()

  const cpu = metrics?.cpu_percent ?? 0
  const mem = metrics?.memory_percent ?? 0
  const criticalEvents = events.filter(e => ecs.severity(e) === 'critical').length

  const combined: EcsEvent[] = [...events, ...alerts]
    .sort((a, b) => a['@timestamp'].localeCompare(b['@timestamp']))
    .slice(-50)

  return (
    <main className="flex-1 p-3 flex flex-col gap-3">

      {/* Row 1: Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
        <StatsCard label="CPU"          value={cpu.toFixed(1)}                              unit="%"    color="cyan"   danger={cpu > 85} />
        <StatsCard label="Memory"       value={mem.toFixed(1)}                              unit="%"    color="purple" danger={mem > 85} />
        <StatsCard label="Disk"         value={metrics?.disk_percent.toFixed(1) ?? '—'}     unit="%"    color="orange" />
        <StatsCard label="Net In"       value={metrics?.network_in_mbps.toFixed(0) ?? '—'}  unit="Mbps" color="green" />
        <StatsCard label="Net Out"      value={metrics?.network_out_mbps.toFixed(0) ?? '—'} unit="Mbps" color="green" />
        <StatsCard label="Detections"   value={alerts.length}                               color="red"  danger={alerts.length > 0} />
        <StatsCard label="Alerts / hr"  value={metrics?.alerts_last_hour ?? '—'}            color="red"  danger={criticalEvents > 0} />
      </div>

      {/* Row 2: Geo map + Network topology */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3" style={{ minHeight: 280 }}>
        <Panel title={`Attack Origin Map  (${arcs.length} arcs)`} className="lg:col-span-3">
          <GeoMap arcs={arcs} />
        </Panel>
        <Panel title="Network Topology" className="lg:col-span-2">
          <NetworkGraph nodes={nodes} edges={edges} />
        </Panel>
      </div>

      {/* Row 3: Metrics + CVE feed */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3" style={{ minHeight: 240 }}>
        <Panel title="System Metrics — Live (60 s)" className="lg:col-span-3">
          <div className="p-2 h-full"><MetricsChart data={history} /></div>
        </Panel>
        <Panel title="CVE Intel Feed  · NVD" className="lg:col-span-2">
          <CveFeed cves={cves} loading={cvesLoading} />
        </Panel>
      </div>

      {/* Row 4: Timeline/Logs + MITRE + Risk/Rules */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3" style={{ minHeight: 260 }}>
        <div className="lg:col-span-5 relative scanline bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col overflow-hidden">
          <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
              <div className="flex gap-1">
                {(['timeline', 'logs'] as const).map(tab => (
                  <button key={tab} onClick={() => setActiveTab(tab)}
                    className={`text-xs px-3 py-1 rounded transition-colors ${activeTab === tab ? 'bg-cyan-500/20 text-cyan-400' : 'text-slate-500 hover:text-slate-300'}`}>
                    {tab === 'timeline' ? 'Event Timeline' : 'Raw Logs'}
                  </button>
                ))}
              </div>
            </div>
            <span className="text-[10px] text-slate-600">{events.length} events · {alerts.length} alerts</span>
          </div>
          <div className="flex-1 overflow-hidden">
            {activeTab === 'timeline'
              ? <div className="p-2 h-full"><EventTimeline events={combined} /></div>
              : <LogViewer events={events.slice(-50)} />}
          </div>
        </div>

        <Panel title="MITRE ATT&CK" className="lg:col-span-3">
          <MitrePanel tactics={tactics} />
        </Panel>

        <div className="lg:col-span-4 relative scanline bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col overflow-hidden">
          <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
              <div className="flex gap-1">
                {(['risk', 'rules'] as const).map(tab => (
                  <button key={tab} onClick={() => setActiveBottomTab(tab)}
                    className={`text-xs px-3 py-1 rounded transition-colors ${activeBottomTab === tab ? 'bg-cyan-500/20 text-cyan-400' : 'text-slate-500 hover:text-slate-300'}`}>
                    {tab === 'risk' ? 'Top Risk Entities' : `Rules (${rules.length})`}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="flex-1 overflow-hidden">
            {activeBottomTab === 'risk' ? <RiskPanel entities={riskEntities} /> : <RulesPanel rules={rules} />}
          </div>
        </div>
      </div>

      {/* Row 5: Alert Feed */}
      <div className="grid grid-cols-1 gap-3" style={{ minHeight: 200 }}>
        <Panel title={`Live Alert Feed  ·  ${criticalEvents} critical / ${alerts.length} rule-driven`}>
          <AlertFeed events={[...events, ...alerts].slice(-60)} onPivot={onPivot} />
        </Panel>
      </div>
    </main>
  )
}
