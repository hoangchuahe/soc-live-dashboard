import { useEffect, useState } from 'react'
import type { RuleSummary } from '../types'

interface Props {
  rules: RuleSummary[]
}

const SEV_DOT: Record<string, string> = {
  low:      'bg-green-500',
  medium:   'bg-yellow-500',
  high:     'bg-orange-500',
  critical: 'bg-red-500',
}

export function RulesPanel({ rules }: Props) {
  if (rules.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600 text-xs">
        Loading rules…
      </div>
    )
  }

  return (
    <ul className="overflow-y-auto h-full divide-y divide-slate-800/60">
      {rules.map(r => (
        <li key={r.id} className="px-3 py-2 hover:bg-slate-800/40 transition-colors">
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${SEV_DOT[r.severity] ?? 'bg-slate-500'}`} />
              <span className="text-xs font-semibold text-slate-300 truncate">{r.title}</span>
            </div>
            <span className="text-[10px] tabular-nums font-bold text-cyan-400 shrink-0">
              {r.fire_count}
            </span>
          </div>
          <div className="flex items-center gap-2 text-[9px] text-slate-500">
            {r.technique_id && <span className="font-mono text-purple-400">{r.technique_id}</span>}
            {r.tactic && <span>{r.tactic}</span>}
            {r.has_threshold && <span className="text-cyan-500">·threshold</span>}
          </div>
        </li>
      ))}
    </ul>
  )
}

export function useRules() {
  const [rules, setRules] = useState<RuleSummary[]>([])

  useEffect(() => {
    const refresh = () => {
      fetch('/api/rules')
        .then(r => r.json())
        .then(d => setRules(d.rules ?? []))
        .catch(() => {})
    }
    refresh()
    const id = setInterval(refresh, 3000)
    return () => clearInterval(id)
  }, [])

  return rules
}
