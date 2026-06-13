import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ModeIndicator } from './ModeIndicator'
import type { HealthStatus } from '../../types'

describe('ModeIndicator', () => {
  it('renders the mode and one dot per source', () => {
    const health: HealthStatus = {
      mode: 'blend',
      sources: [
        { name: 'host.network', available: true, detail: 'ok' },
        { name: 'windows.security', available: false, detail: 'requires admin' },
      ],
    }
    const { container } = render(<ModeIndicator health={health} />)
    expect(screen.getByText('blend')).toBeTruthy()
    expect(container.querySelectorAll('span[title]')).toHaveLength(2)
  })

  it('shows unknown when health is null', () => {
    render(<ModeIndicator health={null} />)
    expect(screen.getByText('unknown')).toBeTruthy()
  })
})
