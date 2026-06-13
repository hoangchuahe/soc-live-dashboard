import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ResultsTable } from './ResultsTable'
import type { EcsEvent } from '../../types'

function evt(id: string, simulated = false): EcsEvent {
  return {
    '@timestamp': '2026-06-14T00:00:00Z',
    event: { id, kind: 'event', category: 'network', severity: 'low' },
    message: `msg ${id}`,
    source: { ip: '1.1.1.1' },
    ...(simulated ? { labels: { provenance: 'simulated' } } : {}),
  }
}

describe('ResultsTable', () => {
  it('renders empty state when no results', () => {
    render(<ResultsTable results={[]} />)
    expect(screen.getByText(/No events in range/)).toBeTruthy()
  })

  it('shows SIM chip only for simulated rows and expands JSON on click', () => {
    render(<ResultsTable results={[evt('a', true), evt('b', false)]} />)
    expect(screen.getAllByText('SIM')).toHaveLength(1)
    fireEvent.click(screen.getByText('msg a'))
    expect(screen.getByText(/"id": "a"/)).toBeTruthy()
  })
})
