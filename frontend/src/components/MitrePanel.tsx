import { useEffect, useState } from 'react'
import type { MitreTactic } from '../types'

interface Props {
  tactics: MitreTactic[]
}

const TACTIC_ABBR: Record<string, string> = {
  'Reconnaissance':       'Recon',
  'Initial Access':       'Init Access',
  'Execution':            'Exec',
  'Persistence':          'Persist',
  'Privilege Escalation': 'Priv Esc',
  'Defense Evasion':      'Def Evasion',
  'Credential Access':    'Cred Access',
  'Discovery':            'Discovery',
  'Lateral Movement':     'Lateral Mv',
  'Collection':           'Collection',
  'Command and Control':  'C2',
  'Exfiltration':         'Exfil',
  'Impact':               'Impact',
}

function heatColor(count: number, max: number): string {
  if (count === 0) return '#0f172a'
  const t = count / Math.max(max, 1)
  if (t > 0.7) return '#7f1d1d'
  if (t > 0.4) return '#92400e'
  if (t > 0.1) return '#1e3a5f'
  return '#172033'
}

export function MitrePanel({ tactics }: Props) {
  const max = Math.max(...tactics.map(t => t.count), 1)

  return (
    <div className="p-3 h-full overflow-y-auto">
      <div className="grid grid-cols-2 gap-1">
        {tactics.map(t => (
          <div
            key={t.name}
            className="rounded px-2 py-1.5 border border-slate-800/60 transition-colors"
            style={{ background: heatColor(t.count, max) }}
            title={`${t.name}: ${t.count} events`}
          >
            <div className="text-[9px] text-slate-400 uppercase tracking-wider truncate">
              {TACTIC_ABBR[t.name] ?? t.name}
            </div>
            <div className="text-xs font-bold tabular-nums" style={{
              color: t.count > 0 ? '#f1f5f9' : '#334155'
            }}>
              {t.count}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2 text-[9px] text-slate-600">
        <span className="w-3 h-3 rounded inline-block bg-[#0f172a] border border-slate-700" />none
        <span className="w-3 h-3 rounded inline-block bg-[#1e3a5f]" />low
        <span className="w-3 h-3 rounded inline-block bg-[#92400e]" />med
        <span className="w-3 h-3 rounded inline-block bg-[#7f1d1d]" />high
      </div>
    </div>
  )
}

export function useMitreTactics() {
  const [tactics, setTactics] = useState<MitreTactic[]>([])

  useEffect(() => {
    const refresh = () => {
      fetch('/api/mitre/tactics')
        .then(r => r.json())
        .then(d => setTactics(d.tactics ?? []))
        .catch(() => {})
    }
    refresh()
    const id = setInterval(refresh, 5000)
    return () => clearInterval(id)
  }, [])

  return tactics
}
