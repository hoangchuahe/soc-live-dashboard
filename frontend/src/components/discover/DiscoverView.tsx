import { useCallback, useEffect, useState } from 'react'
import { useUi } from '../../context/UiContext'
import { rangeFromPreset } from '../../lib/timeRange'
import { matchesProvenance } from '../../lib/provenance'
import { bucketEvents } from '../../lib/histogram'
import { SearchBar } from './SearchBar'
import { EventHistogram } from './EventHistogram'
import { ResultsTable } from './ResultsTable'
import type { EcsEvent } from '../../types'

interface SearchResponse { results: EcsEvent[]; matched: number; from: string; to: string; source: string }
interface ApiError { detail: { detail: string; position: number } }

const BUCKETS = 30

export function DiscoverView() {
  const ui = useUi()
  const [results, setResults] = useState<EcsEvent[]>([])
  const [matched, setMatched] = useState(0)
  const [error, setError] = useState<{ message: string; position: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const [range, setRange] = useState(() => rangeFromPreset('15m'))

  const run = useCallback(async () => {
    if (!ui.discoverQuery.trim()) return
    setLoading(true); setError(null)
    const { from, to } = rangeFromPreset(ui.preset)
    setRange({ from, to })
    const url = `/api/search?q=${encodeURIComponent(ui.discoverQuery)}&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&limit=200`
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
  }, [ui.discoverQuery, ui.preset])

  // run whenever the query or preset changes
  useEffect(() => { void run() }, [run])

  // auto-refresh: re-run the active query on the chosen interval
  useEffect(() => {
    if (ui.refreshInterval === 0 || !ui.discoverQuery.trim()) return
    const id = setInterval(() => { void run() }, ui.refreshInterval * 1000)
    return () => clearInterval(id)
  }, [ui.refreshInterval, ui.discoverQuery, run])

  const filtered = results.filter(e => matchesProvenance(e, ui.provenance))
  const buckets = bucketEvents(filtered, range.from, range.to, BUCKETS)

  return (
    <main className="flex-1 p-3 flex flex-col gap-3">
      <div className="relative scanline bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col overflow-hidden flex-1">
        <div className="px-4 py-2 border-b border-slate-800 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Discover</h2>
        </div>
        <SearchBar query={ui.discoverQuery} onQueryChange={ui.setDiscoverQuery} onRun={() => void run()} loading={loading} error={error} matched={matched} />
        <div className="p-2 border-b border-slate-800"><EventHistogram buckets={buckets} /></div>
        <div className="flex-1 overflow-auto"><ResultsTable results={filtered} /></div>
      </div>
    </main>
  )
}
