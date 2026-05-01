import { ReactNode } from 'react'

interface Props {
  title: string
  children: ReactNode
  className?: string
}

export function Panel({ title, children, className = '' }: Props) {
  return (
    <div className={`relative scanline bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col overflow-hidden ${className}`}>
      <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-widest">{title}</h2>
      </div>
      <div className="flex-1 overflow-hidden">{children}</div>
    </div>
  )
}

export function Header({ status }: { status: 'connecting' | 'connected' | 'disconnected' }) {
  const statusColor = {
    connecting:   'bg-yellow-500',
    connected:    'bg-green-500',
    disconnected: 'bg-red-500',
  }[status]

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <span className="text-cyan-400 text-xl">🛡</span>
        <div>
          <h1 className="text-sm font-bold text-slate-100 tracking-widest uppercase">SOC Live Dashboard</h1>
          <p className="text-xs text-slate-500">Real-time security telemetry</p>
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <span className={`w-2 h-2 rounded-full ${statusColor}`} />
        <span className="uppercase tracking-wider">{status}</span>
      </div>
    </header>
  )
}
