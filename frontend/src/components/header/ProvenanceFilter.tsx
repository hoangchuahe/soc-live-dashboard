import type { Provenance } from '../../lib/provenance'

const SEGMENTS: { v: Provenance; label: string }[] = [
  { v: 'all', label: 'All' }, { v: 'live', label: 'Live' }, { v: 'simulated', label: 'Demo' },
]

export function ProvenanceFilter({ value, onChange }: { value: Provenance; onChange: (p: Provenance) => void }) {
  return (
    <div className="flex items-center rounded border border-slate-700 overflow-hidden">
      {SEGMENTS.map(s => (
        <button key={s.v} onClick={() => onChange(s.v)}
          className={`px-2 py-0.5 text-xs ${value === s.v ? 'bg-cyan-500/20 text-cyan-400' : 'bg-slate-900 text-slate-500 hover:text-slate-300'}`}>
          {s.label}
        </button>
      ))}
    </div>
  )
}
