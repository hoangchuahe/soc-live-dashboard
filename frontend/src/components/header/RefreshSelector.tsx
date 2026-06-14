import type { RefreshInterval } from '../../context/UiContext'

const OPTS: { v: RefreshInterval; label: string }[] = [
  { v: 0, label: 'Off' }, { v: 5, label: '5s' }, { v: 30, label: '30s' }, { v: 60, label: '1m' },
]

export function RefreshSelector({ value, onChange }: { value: RefreshInterval; onChange: (n: RefreshInterval) => void }) {
  return (
    <select
      value={value}
      onChange={e => onChange(Number(e.target.value) as RefreshInterval)}
      className="bg-slate-900 border border-slate-700 rounded px-2 py-0.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
    >
      {OPTS.map(o => <option key={o.v} value={o.v}>{`⟳ ${o.label}`}</option>)}
    </select>
  )
}
