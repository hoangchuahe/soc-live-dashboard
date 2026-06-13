import { Fragment, useState } from 'react'
import type { EcsEvent } from '../../types'
import { ecs } from '../../types'
import { SimChip } from '../SimChip'

const SEV_TEXT: Record<string, string> = {
  low: 'text-green-400', medium: 'text-yellow-400', high: 'text-orange-400', critical: 'text-red-400',
}

function fmt(iso: string) {
  return new Date(iso).toLocaleTimeString('en-GB', { hour12: false })
}

export function ResultsTable({ results }: { results: EcsEvent[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (results.length === 0) {
    return <div className="p-4 text-slate-600 text-sm">No events in range.</div>
  }

  return (
    <table className="w-full text-xs">
      <thead className="text-[10px] uppercase tracking-widest text-slate-500 border-b border-slate-800">
        <tr>
          <th className="text-left px-3 py-2">Time</th>
          <th className="text-left px-3 py-2">Severity</th>
          <th className="text-left px-3 py-2">Source → Dest</th>
          <th className="text-left px-3 py-2">Category</th>
          <th className="text-left px-3 py-2">Dataset</th>
          <th className="text-left px-3 py-2">Message</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-800/60">
        {results.map(e => {
          const expanded = expandedId === e.event.id
          return (
            <Fragment key={e.event.id}>
              <tr onClick={() => setExpandedId(expanded ? null : e.event.id)} className="hover:bg-slate-800/40 cursor-pointer">
                <td className="px-3 py-1.5 tabular-nums text-slate-400">{fmt(e['@timestamp'])}</td>
                <td className={`px-3 py-1.5 ${SEV_TEXT[ecs.severity(e)] ?? 'text-slate-400'}`}>
                  <span className="inline-flex items-center gap-1">{ecs.severity(e)}{ecs.isSimulated(e) && <SimChip />}</span>
                </td>
                <td className="px-3 py-1.5 text-slate-400">{ecs.source(e)}{ecs.dest(e) ? ` → ${ecs.dest(e)}` : ''}</td>
                <td className="px-3 py-1.5 text-slate-400">{e.event.category}</td>
                <td className="px-3 py-1.5 text-slate-500">{ecs.dataset(e) ?? '—'}</td>
                <td className="px-3 py-1.5 text-slate-300 truncate max-w-[280px]">{e.message}</td>
              </tr>
              {expanded && (
                <tr>
                  <td colSpan={6} className="px-3 pb-2">
                    <pre className="text-[10px] text-slate-400 bg-slate-900 rounded p-2 overflow-x-auto">{JSON.stringify(e, null, 2)}</pre>
                  </td>
                </tr>
              )}
            </Fragment>
          )
        })}
      </tbody>
    </table>
  )
}
