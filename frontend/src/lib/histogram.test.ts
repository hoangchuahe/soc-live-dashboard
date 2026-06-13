import { describe, it, expect } from 'vitest'
import { bucketEvents } from './histogram'
import type { EcsEvent } from '../types'

function at(ms: number): EcsEvent {
  return {
    '@timestamp': new Date(ms).toISOString(),
    event: { id: `e${ms}`, kind: 'event', category: 'network', severity: 'low' },
    message: 'm',
  }
}

const FROM = '1970-01-01T00:00:00.000Z'   // 0 ms
const TO = '1970-01-01T00:00:00.100Z'     // 100 ms

describe('bucketEvents', () => {
  it('creates N contiguous buckets spanning the window', () => {
    const b = bucketEvents([], FROM, TO, 10)
    expect(b).toHaveLength(10)
    expect(b[0].t0).toBe(0)
    expect(b[0].t1).toBe(10)
    expect(b[9].t1).toBe(100)
    expect(b.every(x => x.count === 0)).toBe(true)
  })

  it('counts events into the right bucket; right edge lands in the last bucket', () => {
    const b = bucketEvents([at(0), at(5), at(15), at(100)], FROM, TO, 10)
    expect(b[0].count).toBe(2)   // 0 and 5
    expect(b[1].count).toBe(1)   // 15
    expect(b[9].count).toBe(1)   // 100 clamped into last
  })

  it('ignores events outside the window and bad timestamps', () => {
    const bad: EcsEvent = { '@timestamp': 'nope', event: { id: 'x', kind: 'event', category: 'n', severity: 'low' }, message: 'm' }
    const b = bucketEvents([at(-10), at(200), bad, at(50)], FROM, TO, 10)
    const total = b.reduce((s, x) => s + x.count, 0)
    expect(total).toBe(1)        // only at(50)
    expect(b[5].count).toBe(1)
  })
})
