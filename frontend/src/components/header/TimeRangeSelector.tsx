import type { RangePreset } from '../../context/UiContext'

const PRESETS: RangePreset[] = ['5m', '15m', '1h', '24h']

export function TimeRangeSelector({ value, onChange }: { value: RangePreset; onChange: (p: RangePreset) => void }) {
  return (
    <div className="flex items-center gap-1">
      {PRESETS.map(p => (
        <button key={p} onClick={() => onChange(p)}
          className={`px-2 py-0.5 rounded border text-xs ${value === p ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30' : 'bg-slate-900 text-slate-500 border-slate-700 hover:text-slate-300'}`}>
          {p}
        </button>
      ))}
    </div>
  )
}
