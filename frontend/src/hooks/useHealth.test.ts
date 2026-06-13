import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useHealth } from './useHealth'
import type { HealthStatus } from '../types'

const SAMPLE: HealthStatus = {
  mode: 'blend',
  sources: [{ name: 'host.network', available: true, detail: 'ok' }],
}

describe('useHealth', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches /health on mount and returns it', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ json: () => Promise.resolve(SAMPLE) })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useHealth(100000))
    await waitFor(() => expect(result.current?.mode).toBe('blend'))
    expect(fetchMock).toHaveBeenCalledWith('/health')
  })

  it('returns null when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))
    const { result } = renderHook(() => useHealth(100000))
    await waitFor(() => expect(result.current).toBeNull())
  })
})
