// frontend/src/components/SearchPanel.tsx
import { useEffect, useState } from 'react'
import type { EcsEvent } from '../types'
import { ecs } from '../types'
import { rangeFromPreset, type Preset } from '../lib/timeRange'

interface Props {
  open: boolean
  initialQuery: string
  initialPreset: Preset
  onClose: () => void
}

interface SearchResponse {
  results: EcsEvent[]
  matched: number
  from: string
  to: string
  source: string
}

interface ApiError {
  detail: { detail: string; position: number }
}

export function SearchPanel({ open, initialQuery, initialPreset, onClose }: Props) {
  const [query, setQuery] = useState(initialQuery)
  const [preset, setPreset] = useState<Preset>(initialPreset)
  const [results, setResults] = useState<EcsEvent[]>([])
  const [matched, setMatched] = useState(0)
  const [error, setError] = useState<{ message: string; position: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => { setQuery(initialQuery) }, [initialQuery])
  useEffect(() => { setPreset(initialPreset) }, [initialPreset])

  async function run() {
    if (!query.trim() || preset === 'custom') return
    setLoading(true); setError(null)
    const { from, to } = rangeFromPreset(preset)
    const url = `/api/search?q=${encodeURIComponent(query)}&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&limit=200`
    try {
      const r = await fetch(url)
      if (r.status === 400) {
        const body = await r.json() as ApiError
        setError({ message: body.detail.detail, position: body.detail.position })
        setResults([]); setMatched(0)
      } else {
        const body = await r.json() as SearchResponse
        setResults(body.results); setMatched(body.matched)
      }
    } catch (e) {
      setError({ message: String(e), position: 0 })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (open) void run() /* eslint-disable-next-line */ }, [open, initialQuery, initialPreset])

  function copyLink() {
    const u = new URL(window.location.href)
    u.searchParams.set('q', query)
    u.searchParams.set('preset', preset)
    void navigator.clipboard.writeText(u.toString())
  }

  if (!open) return null

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[480px] bg-slate-950 border-l border-slate-800 shadow-2xl z-40 flex flex-col">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
          <h2 className="text-sm font-semibold text-slate-200">Investigation Search</h2>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-200 text-lg leading-none">×</button>
      </div>

      <div className="px-4 py-3 space-y-2 border-b border-slate-800">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') void run() }}
          placeholder='source.ip:"10.0.0.5" AND event.severity:high'
          className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
        />
        <div className="flex items-center gap-2 text-xs">
          {(['5m', '15m', '1h', '24h'] as const).map(p => (
            <button
              key={p}
              onClick={() => setPreset(p)}
              className={`px-2 py-0.5 rounded border ${preset === p
                ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30'
                : 'bg-slate-900 text-slate-500 border-slate-700 hover:text-slate-300'}`}
            >{p}</button>
          ))}
          <button onClick={() => void run()} className="ml-auto px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/30">
            {loading ? '…' : 'Run'}
          </button>
          <button onClick={copyLink} className="px-2 py-0.5 rounded text-slate-500 hover:text-slate-300">copy link</button>
        </div>
        {error && (
          <div className="text-xs text-red-400 font-mono">
            {error.message} <span className="text-slate-500">(col {error.position})</span>
          </div>
        )}
        {!error && <div className="text-[10px] text-slate-500">{matched} matched</div>}
      </div>

      <ul className="flex-1 overflow-y-auto divide-y divide-slate-800/60">
        {results.map(e => {
          const expanded = expandedId === e.event.id
          return (
            <li key={e.event.id} className="px-4 py-2 hover:bg-slate-800/40">
              <button
                onClick={() => setExpandedId(expanded ? null : e.event.id)}
                className="w-full text-left"
              >
                <div className="flex items-center justify-between text-[10px] text-slate-500 tabular-nums">
                  <span>{new Date(e['@timestamp']).toLocaleTimeString('en-GB', { hour12: false })}</span>
                  <span className="text-slate-600">{ecs.severity(e)}</span>
                </div>
                <div className="text-xs text-slate-300 truncate">{e.message}</div>
                <div className="text-[10px] text-slate-600">{ecs.source(e)}{ecs.dest(e) ? ` → ${ecs.dest(e)}` : ''}</div>
              </button>
              {expanded && (
                <pre className="mt-1 text-[10px] text-slate-400 bg-slate-900 rounded p-2 overflow-x-auto">
                  {JSON.stringify(e, null, 2)}
                </pre>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
