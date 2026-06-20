import { describe, it, expect } from 'vitest'
import { ecs, type EcsEvent } from './index'

const base: EcsEvent = {
  '@timestamp': '2026-06-21T00:00:00Z',
  event: { id: 'e1', kind: 'alert', category: 'detection', severity: 'critical' },
  message: 'm',
}

describe('ecs correlation helpers', () => {
  it('detects a correlated alert and reads its stages', () => {
    const e: EcsEvent = {
      ...base,
      correlation: {
        rule_id: 'corr-0001-multistage-intrusion',
        stages: [{ rule_id: 'rule-0001-auth-brute', title: 'Authentication Brute Force' }],
      },
    }
    expect(ecs.isCorrelation(e)).toBe(true)
    expect(ecs.correlation(e)?.stages.length).toBe(1)
  })

  it('returns false / null for a plain alert', () => {
    expect(ecs.isCorrelation(base)).toBe(false)
    expect(ecs.correlation(base)).toBeNull()
  })
})
