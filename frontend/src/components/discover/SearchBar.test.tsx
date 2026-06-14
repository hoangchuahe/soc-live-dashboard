import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SearchBar } from './SearchBar'

describe('SearchBar', () => {
  it('shows the parse-error position', () => {
    render(<SearchBar query="x" preset="15m" onQueryChange={() => {}} onRun={() => {}} loading={false}
      error={{ message: 'unexpected token', position: 7 }} matched={0} />)
    expect(screen.getByText(/unexpected token/)).toBeTruthy()
    expect(screen.getByText(/col 7/)).toBeTruthy()
  })

  it('runs on button click', () => {
    const onRun = vi.fn()
    render(<SearchBar query="x" preset="15m" onQueryChange={() => {}} onRun={onRun} loading={false} error={null} matched={3} />)
    fireEvent.click(screen.getByText('Run'))
    expect(onRun).toHaveBeenCalledOnce()
  })
})
