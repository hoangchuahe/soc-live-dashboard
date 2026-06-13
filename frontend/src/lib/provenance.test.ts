import { describe, it, expect } from 'vitest'
import { matchesProvenance } from './provenance'
import type { EcsEvent } from '../types'

function evt(provenance?: 'live' | 'simulated'): EcsEvent {
  return {
    '@timestamp': '2026-06-14T00:00:00Z',
    event: { id: 'e1', kind: 'event', category: 'network', severity: 'low' },
    message: 'm',
    ...(provenance ? { labels: { provenance } } : {}),
  }
}

describe('matchesProvenance', () => {
  it('all matches everything', () => {
    expect(matchesProvenance(evt(), 'all')).toBe(true)
    expect(matchesProvenance(evt('simulated'), 'all')).toBe(true)
  })
  it('live matches live (incl. unlabelled) only', () => {
    expect(matchesProvenance(evt(), 'live')).toBe(true)
    expect(matchesProvenance(evt('simulated'), 'live')).toBe(false)
  })
  it('simulated matches simulated only', () => {
    expect(matchesProvenance(evt('simulated'), 'simulated')).toBe(true)
    expect(matchesProvenance(evt(), 'simulated')).toBe(false)
  })
})
