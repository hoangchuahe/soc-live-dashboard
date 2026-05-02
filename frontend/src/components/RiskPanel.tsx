import { useEffect, useState } from 'react'
import type { RiskEntity } from '../types'

interface Props {
  entities: RiskEntity[]
}

function scoreColor(score: number): string {
  if (score >= 75) return 'text-red-400 bg-red-500/10'
  if (score >= 40) return 'text-orange-400 bg-orange-500/10'
  if (score >= 15) return 'text-yellow-400 bg-yellow-500/10'
  return 'text-slate-400 bg-slate-700/30'
}

function scoreBar(score: number): number {
  return Math.min(100, score)
}

export function RiskPanel({ entities }: Props) {
  if (entities.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600 text-xs text-center p-4">
        Risk scores will appear once detection rules fire
      </div>
    )
  }

  return (
    <ul className="overflow-y-auto h-full divide-y divide-slate-800/60">
      {entities.map((e, i) => (
        <li key={e.name} className="px-3 py-2 hover:bg-slate-800/40 transition-colors">
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-[9px] text-slate-600 tabular-nums shrink-0">#{i + 1}</span>
              <span className="text-xs font-mono text-slate-300 truncate" title={e.name}>{e.name}</span>
            </div>
            <span className={`text-xs font-bold tabular-nums px-2 py-0.5 rounded ${scoreColor(e.score)}`}>
              {e.score.toFixed(1)}
            </span>
          </div>
          <div className="h-1 bg-slate-800 rounded overflow-hidden">
            <div
              className="h-full transition-all duration-500"
              style={{
                width: `${scoreBar(e.score)}%`,
                background: e.score >= 75 ? '#ef4444' : e.score >= 40 ? '#f97316' : e.score >= 15 ? '#eab308' : '#475569',
              }}
            />
          </div>
          <div className="flex items-center justify-between text-[9px] text-slate-600 mt-0.5">
            <span>{e.rule_count} rule{e.rule_count !== 1 ? 's' : ''} contributing</span>
            <span>{e.last_updated_seconds_ago.toFixed(0)}s ago</span>
          </div>
        </li>
      ))}
    </ul>
  )
}

export function useRiskTop() {
  const [entities, setEntities] = useState<RiskEntity[]>([])

  useEffect(() => {
    const refresh = () => {
      fetch('/api/risk/top?n=10')
        .then(r => r.json())
        .then(d => setEntities(d.entities ?? []))
        .catch(() => {})
    }
    refresh()
    const id = setInterval(refresh, 3000)
    return () => clearInterval(id)
  }, [])

  return entities
}
