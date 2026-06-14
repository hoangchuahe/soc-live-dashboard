import { describe, it, expect } from 'vitest'
import { ecs } from './index'
import type { EcsEvent } from './index'

function evt(over: Partial<EcsEvent> = {}): EcsEvent {
  return {
    '@timestamp': '2026-06-14T00:00:00Z',
    event: { id: 'e1', kind: 'event', category: 'network', severity: 'low' },
    message: 'm',
    ...over,
  }
}

describe('ecs provenance/dataset accessors', () => {
  it('defaults provenance to live when labels absent', () => {
    expect(ecs.provenance(evt())).toBe('live')
    expect(ecs.isSimulated(evt())).toBe(false)
  })

  it('reads simulated provenance from labels', () => {
    const e = evt({ labels: { provenance: 'simulated' } })
    expect(ecs.provenance(e)).toBe('simulated')
    expect(ecs.isSimulated(e)).toBe(true)
  })

  it('reads event.dataset, or null', () => {
    expect(ecs.dataset(evt())).toBeNull()
    expect(ecs.dataset(evt({ event: { id: 'e', kind: 'event', category: 'network', severity: 'low', dataset: 'host.network' } }))).toBe('host.network')
  })
})
