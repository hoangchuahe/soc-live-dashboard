import { useEffect, useState } from 'react'
import type { HealthStatus } from '../types'

export function useHealth(intervalMs = 5000): HealthStatus | null {
  const [health, setHealth] = useState<HealthStatus | null>(null)

  useEffect(() => {
    let active = true
    const load = () => {
      fetch('/health')
        .then(r => r.json())
        .then((d: HealthStatus) => { if (active) setHealth(d) })
        .catch(() => { if (active) setHealth(null) })
    }
    load()
    const id = setInterval(load, intervalMs)
    return () => { active = false; clearInterval(id) }
  }, [intervalMs])

  return health
}
