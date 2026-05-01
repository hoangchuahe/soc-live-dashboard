import { useEffect, useState } from 'react'
import type { CveItem } from '../types'

const SEV_STYLE: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high:     'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium:   'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low:      'bg-green-500/20 text-green-400 border-green-500/30',
  unknown:  'bg-slate-700/40 text-slate-400 border-slate-600/30',
}

function fmtDate(iso: string) {
  return iso ? iso.slice(0, 10) : '—'
}

interface Props {
  cves: CveItem[]
  loading: boolean
}

export function CveFeed({ cves, loading }: Props) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500 text-sm">
        Fetching NVD feed…
      </div>
    )
  }
  if (cves.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600 text-xs">
        CVE feed unavailable (NVD API offline or rate-limited)
      </div>
    )
  }

  return (
    <ul className="overflow-y-auto h-full divide-y divide-slate-800/60">
      {cves.map(cve => (
        <li key={cve.id} className="px-4 py-2.5 hover:bg-slate-800/40 transition-colors">
          <div className="flex items-center justify-between gap-2 mb-1">
            <a
              href={`https://nvd.nist.gov/vuln/detail/${cve.id}`}
              target="_blank"
              rel="noreferrer"
              className="text-xs font-mono font-semibold text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              {cve.id}
            </a>
            <div className="flex items-center gap-2">
              {cve.cvss !== null && (
                <span className="text-[10px] font-bold text-slate-300 tabular-nums">
                  {cve.cvss.toFixed(1)}
                </span>
              )}
              <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border ${SEV_STYLE[cve.severity]}`}>
                {cve.severity.toUpperCase()}
              </span>
            </div>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-2">{cve.description}</p>
          <div className="text-[10px] text-slate-600 mt-1">{fmtDate(cve.published)}</div>
        </li>
      ))}
    </ul>
  )
}

export function useCves() {
  const [cves, setCves] = useState<CveItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/cves')
      .then(r => r.json())
      .then(d => { setCves(d.cves ?? []); setLoading(false) })
      .catch(() => setLoading(false))

    // Refresh hourly (NVD cache TTL)
    const id = setInterval(() => {
      fetch('/api/cves')
        .then(r => r.json())
        .then(d => setCves(d.cves ?? []))
        .catch(() => {})
    }, 60 * 60 * 1000)

    return () => clearInterval(id)
  }, [])

  return { cves, loading }
}
