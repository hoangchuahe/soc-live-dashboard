import type { EcsEvent } from '../types'

export interface Bucket {
  t0: number   // bucket start (ms epoch)
  t1: number   // bucket end (ms epoch)
  count: number
}

export function bucketEvents(
  events: EcsEvent[],
  fromIso: string,
  toIso: string,
  bucketCount: number,
): Bucket[] {
  const from = new Date(fromIso).getTime()
  const to = new Date(toIso).getTime()
  const span = Math.max(1, to - from)
  const width = span / bucketCount

  const buckets: Bucket[] = Array.from({ length: bucketCount }, (_, i) => ({
    t0: from + i * width,
    t1: from + (i + 1) * width,
    count: 0,
  }))

  for (const e of events) {
    const t = new Date(e['@timestamp']).getTime()
    if (Number.isNaN(t) || t < from || t > to) continue
    let idx = Math.floor((t - from) / width)
    if (idx >= bucketCount) idx = bucketCount - 1   // include the right edge
    if (idx < 0) idx = 0
    buckets[idx].count++
  }

  return buckets
}
