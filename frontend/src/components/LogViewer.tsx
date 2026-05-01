import type { SecurityEvent } from '../types'

interface Props {
  events: SecurityEvent[]
}

const FORMAT_BADGE: Record<string, string> = {
  winevent: 'bg-blue-500/20 text-blue-400',
  syslog:   'bg-green-500/20 text-green-400',
  netflow:  'bg-cyan-500/20 text-cyan-400',
  cef:      'bg-purple-500/20 text-purple-400',
}

export function LogViewer({ events }: Props) {
  const withLogs = events.filter(e => e.raw_log)

  if (withLogs.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600 text-sm font-mono">
        Waiting for log events…
      </div>
    )
  }

  return (
    <div className="overflow-y-auto h-full font-mono text-[10px] p-2 space-y-0.5">
      {[...withLogs].reverse().map(e => (
        <div
          key={e.id}
          className="flex items-start gap-2 px-2 py-1 rounded hover:bg-slate-800/50 transition-colors"
        >
          <span className={`shrink-0 px-1.5 py-0.5 rounded text-[8px] font-semibold ${FORMAT_BADGE[e.log_format] ?? 'bg-slate-700 text-slate-400'}`}>
            {e.log_format.toUpperCase()}
          </span>
          <span className="text-slate-500 shrink-0">{e.timestamp.slice(11, 19)}</span>
          <span className="text-slate-300 break-all leading-relaxed">{e.raw_log}</span>
        </div>
      ))}
    </div>
  )
}
