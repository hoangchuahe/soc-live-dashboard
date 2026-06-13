import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { UiProvider, useUi } from './UiContext'

function Probe() {
  const ui = useUi()
  return (
    <div>
      <span data-testid="view">{ui.view}</span>
      <span data-testid="prov">{ui.provenance}</span>
      <span data-testid="query">{ui.discoverQuery}</span>
      <button onClick={() => ui.openDiscoverWith('source.ip:"1.2.3.4"')}>open</button>
      <button onClick={() => ui.setProvenance('simulated')}>sim</button>
    </div>
  )
}

describe('UiContext', () => {
  it('provides defaults', () => {
    render(<UiProvider><Probe /></UiProvider>)
    expect(screen.getByTestId('view').textContent).toBe('dashboard')
    expect(screen.getByTestId('prov').textContent).toBe('all')
  })

  it('openDiscoverWith sets the query and switches view', () => {
    render(<UiProvider><Probe /></UiProvider>)
    fireEvent.click(screen.getByText('open'))
    expect(screen.getByTestId('view').textContent).toBe('discover')
    expect(screen.getByTestId('query').textContent).toBe('source.ip:"1.2.3.4"')
  })

  it('setProvenance updates the filter', () => {
    render(<UiProvider><Probe /></UiProvider>)
    fireEvent.click(screen.getByText('sim'))
    expect(screen.getByTestId('prov').textContent).toBe('simulated')
  })
})
