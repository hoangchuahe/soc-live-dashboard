interface Props {
  label: string
  value: string | number
  unit?: string
  color?: 'cyan' | 'purple' | 'orange' | 'red' | 'green'
  danger?: boolean
}

const colorMap = {
  cyan:   'border-cyan-500/30 text-cyan-400',
  purple: 'border-purple-500/30 text-purple-400',
  orange: 'border-orange-500/30 text-orange-400',
  red:    'border-red-500/30 text-red-400',
  green:  'border-green-500/30 text-green-400',
}

export function StatsCard({ label, value, unit, color = 'cyan', danger }: Props) {
  return (
    <div className={`relative scanline bg-slate-900/80 border rounded-lg p-4 flex flex-col gap-1 ${colorMap[color]} ${danger ? 'animate-pulse' : ''}`}>
      <span className="text-xs text-slate-500 uppercase tracking-widest">{label}</span>
      <div className="flex items-end gap-1">
        <span className="text-2xl font-bold tabular-nums">{value}</span>
        {unit && <span className="text-sm text-slate-500 mb-0.5">{unit}</span>}
      </div>
    </div>
  )
}
