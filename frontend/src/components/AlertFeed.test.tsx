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
