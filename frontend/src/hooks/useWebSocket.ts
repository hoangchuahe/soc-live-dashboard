import { useEffect, useRef, useState, useCallback } from 'react'
import type { WsFrame } from '../types'

type Status = 'connecting' | 'connected' | 'disconnected'

export function useWebSocket(url: string) {
  const [frame, setFrame] = useState<WsFrame | null>(null)
  const [status, setStatus] = useState<Status>('connecting')
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout>>()

  const connect = useCallback(() => {
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setStatus('connected')

    ws.onmessage = (e) => {
      try {
        setFrame(JSON.parse(e.data) as WsFrame)
      } catch {
        // ignore malformed frames
      }
    }

    ws.onclose = () => {
      setStatus('disconnected')
      retryRef.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => ws.close()
  }, [url])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { frame, status }
}
