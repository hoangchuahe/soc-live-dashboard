import type { EcsEvent } from '../types'
import { ecs } from '../types'

export type Provenance = 'all' | 'live' | 'simulated'

export function matchesProvenance(e: EcsEvent, filter: Provenance): boolean {
  if (filter === 'all') return true
  return ecs.provenance(e) === filter
}
