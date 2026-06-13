import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ProvenanceFilter } from './ProvenanceFilter'

describe('ProvenanceFilter', () => {
  it('calls onChange with the chosen provenance', () => {
    const onChange = vi.fn()
    render(<ProvenanceFilter value="all" onChange={onChange} />)
    fireEvent.click(screen.getByText('Live'))
    expect(onChange).toHaveBeenCalledWith('live')
    fireEvent.click(screen.getByText('Demo'))
    expect(onChange).toHaveBeenCalledWith('simulated')
  })
})
