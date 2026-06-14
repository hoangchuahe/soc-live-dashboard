import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { UiProvider } from '../../context/UiContext'
import { DiscoverView } from './DiscoverView'

describe('DiscoverView', () => {
  it('renders the Discover panel and empty state when no query', () => {
    render(<UiProvider><DiscoverView /></UiProvider>)
    expect(screen.getByText('Discover')).toBeTruthy()
    expect(screen.getByText(/No events in range/)).toBeTruthy()
  })
})
