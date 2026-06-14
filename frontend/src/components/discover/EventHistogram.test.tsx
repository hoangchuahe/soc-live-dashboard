import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { EventHistogram } from './EventHistogram'
import type { Bucket } from '../../lib/histogram'

describe('EventHistogram', () => {
  it('renders one rect per bucket', () => {
    const buckets: Bucket[] = Array.from({ length: 6 }, (_, i) => ({ t0: i, t1: i + 1, count: i }))
    const { container } = render(<EventHistogram buckets={buckets} />)
    expect(container.querySelectorAll('rect')).toHaveLength(6)
  })
})
