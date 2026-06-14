import type { HealthStatus } from '../../types'

export function ModeIndicator({ health }: { health: HealthStatus | null }) {
  const mode = health?.mode ?? 'unknown'
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] font-bold uppercase tracking-widest text-cyan-400">{mode}</span>
      <div className="flex items-center gap-1">
        {(health?.sources ?? []).map(s => (
          <span key={s.name} title={`${s.name}: ${s.detail}`}
            className={`w-2 h-2 rounded-full ${s.available ? 'bg-green-500' : 'bg-red-500'}`} />
        ))}
      </div>
    </div>
  )
}
