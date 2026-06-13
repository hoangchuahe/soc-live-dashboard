import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { Preset } from '../lib/timeRange'
import type { Provenance } from '../lib/provenance'

export type RangePreset = Exclude<Preset, 'custom'>   // '5m' | '15m' | '1h' | '24h'
export type RefreshInterval = 0 | 5 | 30 | 60

export interface UiContextValue {
  view: 'dashboard' | 'discover'
  preset: RangePreset
  refreshInterval: RefreshInterval
  provenance: Provenance
  livePaused: boolean
  discoverQuery: string
  setView: (v: 'dashboard' | 'discover') => void
  setPreset: (p: RangePreset) => void
  setRefreshInterval: (n: RefreshInterval) => void
  setProvenance: (p: Provenance) => void
  toggleLivePaused: () => void
  setDiscoverQuery: (q: string) => void
  openDiscoverWith: (query: string) => void
}

const UiContext = createContext<UiContextValue | null>(null)

export function UiProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState<'dashboard' | 'discover'>('dashboard')
  const [preset, setPreset] = useState<RangePreset>('15m')
  const [refreshInterval, setRefreshInterval] = useState<RefreshInterval>(0)
  const [provenance, setProvenance] = useState<Provenance>('all')
  const [livePaused, setLivePaused] = useState(false)
  const [discoverQuery, setDiscoverQuery] = useState('')

  const toggleLivePaused = useCallback(() => setLivePaused(p => !p), [])
  const openDiscoverWith = useCallback((query: string) => {
    setDiscoverQuery(query)
    setView('discover')
  }, [])

  const value = useMemo<UiContextValue>(() => ({
    view, preset, refreshInterval, provenance, livePaused, discoverQuery,
    setView, setPreset, setRefreshInterval, setProvenance,
    toggleLivePaused, setDiscoverQuery, openDiscoverWith,
  }), [view, preset, refreshInterval, provenance, livePaused, discoverQuery, toggleLivePaused, openDiscoverWith])

  return <UiContext.Provider value={value}>{children}</UiContext.Provider>
}

export function useUi(): UiContextValue {
  const ctx = useContext(UiContext)
  if (!ctx) throw new Error('useUi must be used within <UiProvider>')
  return ctx
}
