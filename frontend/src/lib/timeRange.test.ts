import { describe, it, expect } from 'vitest'
import { rangeFromPreset, isValidIso } from './timeRange'

describe('timeRange', () => {
  it('computes a from/to window for a preset', () => {
    const now = new Date('2026-06-14T00:00:00.000Z')
    const r = rangeFromPreset('15m', now)
    expect(r.to).toBe('2026-06-14T00:00:00.000Z')
    expect(r.from).toBe('2026-06-13T23:45:00.000Z')
  })

  it('isValidIso rejects junk and accepts ISO', () => {
    expect(isValidIso('nonsense')).toBe(false)
    expect(isValidIso('2026-06-14T00:00:00Z')).toBe(true)
  })
})
