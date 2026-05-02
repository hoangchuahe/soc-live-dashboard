import type { EcsEvent } from '../types'
import { ecs } from '../types'

interface Props {
  events: EcsEvent[]
}

const SEV_BADGE: Record<string, string> = {
  low:      'bg-green-500/20 text-green-400 border-green-500/30',
  medium:   'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  high:     'bg-orange-500/20 text-orange-400 border-orange-500/30',
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-GB', { hour12: false })
}

export function AlertFeed({ events }: Props) {
  if (events.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600 text-sm">
        Awaiting events…
      </div>
    )
  }

  return (
    <ul className="overflow-y-auto h-full divide-y divide-slate-800/60">
      {[...events].reverse().map(e => {
        const sev = ecs.severity(e)
        return (
          <li key={e.event.id} className="px-4 py-2.5 hover:bg-slate-800/40 transition-colors">
            <div className="flex items-center justify-between gap-2 mb-1">
              <div className="flex items-center gap-1.5">
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${SEV_BADGE[sev]}`}>
                  {sev.toUpperCase()}
                </span>
                {ecs.isAlert(e) && (
                  <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                    ALERT
                  </span>
                )}
                {ecs.technique(e) && (
                  <span className="text-[9px] font-mono text-purple-400">{ecs.technique(e)}</span>
                )}
              </div>
              <span className="text-[10px] text-slate-500 tabular-nums">{fmtTime(e['@timestamp'])}</span>
            </div>
            <div className="text-xs font-semibold text-slate-300 truncate">
              {e.rule?.name ?? ecs.type(e)}
            </div>
            <div className="text-[11px] text-slate-500 truncate">{e.message}</div>
            <div className="text-[10px] text-slate-600 mt-0.5">
              {ecs.source(e)}{ecs.dest(e) ? ` → ${ecs.dest(e)}` : ''}
            </div>
          </li>
        )
      })}
    </ul>
  )
}
