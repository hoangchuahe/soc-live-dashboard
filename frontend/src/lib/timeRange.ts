// frontend/src/lib/timeRange.ts
export type Preset = '5m' | '15m' | '1h' | '24h' | 'custom'

const PRESET_MINUTES: Record<Exclude<Preset, 'custom'>, number> = {
  '5m': 5,
  '15m': 15,
  '1h': 60,
  '24h': 60 * 24,
}

export interface TimeRange {
  from: string   // ISO 8601 UTC
  to: string     // ISO 8601 UTC
}

export function rangeFromPreset(preset: Exclude<Preset, 'custom'>, now = new Date()): TimeRange {
  const minutes = PRESET_MINUTES[preset]
  const to = now
  const from = new Date(to.getTime() - minutes * 60_000)
  return { from: from.toISOString(), to: to.toISOString() }
}

export function isValidIso(s: string): boolean {
  const d = new Date(s)
  return !isNaN(d.getTime())
}
