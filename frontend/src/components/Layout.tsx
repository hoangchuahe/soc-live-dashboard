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
