import { useUi } from '../../context/UiContext'
import { useHealth } from '../../hooks/useHealth'
import { TimeRangeSelector } from './TimeRangeSelector'
import { RefreshSelector } from './RefreshSelector'
import { ProvenanceFilter } from './ProvenanceFilter'
import { ModeIndicator } from './ModeIndicator'

const STATUS_COLOR = { connecting: 'bg-yellow-500', connected: 'bg-green-500', disconnected: 'bg-red-500' } as const

export function DashboardHeader({ status }: { status: 'connecting' | 'connected' | 'disconnected' }) {
  const ui = useUi()
  const health = useHealth()

  return (
    <header className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-30">
      <div className="flex items-center gap-2 mr-1">
        <span className="text-cyan-400 text-lg">🛡</span>
        <h1 className="text-sm font-bold text-slate-100 tracking-widest uppercase">SOC</h1>
      </div>

      <div className="flex items-center rounded border border-slate-700 overflow-hidden">
        {(['dashboard', 'discover'] as const).map(v => (
          <button key={v} onClick={() => ui.setView(v)}
            className={`px-3 py-0.5 text-xs capitalize ${ui.view === v ? 'bg-cyan-500/20 text-cyan-400' : 'bg-slate-900 text-slate-500 hover:text-slate-300'}`}>
            {v}
          </button>
        ))}
      </div>

      <TimeRangeSelector value={ui.preset} onChange={ui.setPreset} />
      <RefreshSelector value={ui.refreshInterval} onChange={ui.setRefreshInterval} />
      <ProvenanceFilter value={ui.provenance} onChange={ui.setProvenance} />

      <button onClick={ui.toggleLivePaused}
        className={`px-2 py-0.5 rounded border text-xs ${ui.livePaused ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' : 'bg-slate-900 text-slate-500 border-slate-700 hover:text-slate-300'}`}>
        {ui.livePaused ? '▶ Resume' : '⏸ Pause'}
      </button>

      <div className="ml-auto flex items-center gap-3">
        <ModeIndicator health={health} />
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <span className={`w-2 h-2 rounded-full ${STATUS_COLOR[status]}`} />
          <span className="uppercase tracking-wider">{status}</span>
        </div>
      </div>
    </header>
  )
}
