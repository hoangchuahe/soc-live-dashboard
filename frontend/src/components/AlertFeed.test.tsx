import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AlertFeed } from './AlertFeed'
import type { EcsEvent } from '../types'

function evt(id: string, simulated: boolean): EcsEvent {
  return {
    '@timestamp': '2026-06-14T00:00:00Z',
    event: { id, kind: 'event', category: 'authentication', severity: 'high' },
    message: `msg ${id}`,
    source: { ip: '1.2.3.4' },
    ...(simulated ? { labels: { provenance: 'simulated' } } : {}),
  }
}

describe('AlertFeed SIM chip', () => {
  it('shows a SIM chip only for simulated events', () => {
    render(<AlertFeed events={[evt('a', true), evt('b', false)]} />)
    expect(screen.getAllByText('SIM')).toHaveLength(1)
  })
})

describe('AlertFeed multi-stage correlation', () => {
  function correlatedAlert(): EcsEvent {
    return {
      '@timestamp': '2026-06-21T00:00:00Z',
      event: { id: 'corr-1', kind: 'alert', category: 'detection', severity: 'critical' },
      message: 'Multi-stage attack on WEB-PROD-01',
      correlation: {
        rule_id: 'corr-0001-multistage-intrusion',
        stages: [
          { rule_id: 'rule-0001-auth-brute', title: 'Authentication Brute Force', technique_id: 'T1110.001' },
          { rule_id: 'rule-0004-c2-beacon', title: 'Malware C2 Beacon Detected', technique_id: 'T1071.001' },
        ],
      },
    }
  }

  it('renders a MULTI-STAGE badge and the stage chain for a correlated alert', () => {
    const { container } = render(<AlertFeed events={[correlatedAlert()]} />)
    expect(screen.getByText(/MULTI-STAGE/)).toBeTruthy()
    expect(container.textContent).toContain('Authentication Brute Force')
    expect(container.textContent).toContain('Malware C2 Beacon Detected')
    expect(container.textContent).toContain('(T1110.001)')
  })

  it('shows no MULTI-STAGE badge for a plain (non-correlated) event', () => {
    render(<AlertFeed events={[evt('p', false)]} />)
    expect(screen.queryByText(/MULTI-STAGE/)).toBeNull()
  })
})
