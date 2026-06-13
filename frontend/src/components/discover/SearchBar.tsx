interface Props {
  query: string
  onQueryChange: (q: string) => void
  onRun: () => void
  loading: boolean
  error: { message: string; position: number } | null
  matched: number
}

export function SearchBar({ query, onQueryChange, onRun, loading, error, matched }: Props) {
  function copyLink() {
    const u = new URL(window.location.href)
    u.searchParams.set('q', query)
    void navigator.clipboard.writeText(u.toString())
  }

  return (
    <div className="px-3 py-2 space-y-2 border-b border-slate-800">
      <div className="flex items-center gap-2">
        <input
          value={query}
          onChange={e => onQueryChange(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') onRun() }}
          placeholder='source.ip:"10.0.0.5" AND event.severity:high'
          className="flex-1 bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
        />
        <button onClick={onRun} className="px-3 py-1.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/30 text-xs">
          {loading ? '…' : 'Run'}
        </button>
        <button onClick={copyLink} className="px-2 py-1.5 rounded text-slate-500 hover:text-slate-300 text-xs">copy link</button>
      </div>
      {error
        ? <div className="text-xs text-red-400 font-mono">{error.message} <span className="text-slate-500">(col {error.position})</span></div>
        : <div className="text-[10px] text-slate-500">{matched} matched</div>}
    </div>
  )
}
