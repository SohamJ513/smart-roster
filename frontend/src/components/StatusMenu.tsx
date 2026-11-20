import { useEffect, useRef } from 'react'
import { STATUS_META, STATUS_ORDER } from '../lib/status'
import type { Status } from '../types'

export interface MenuTarget { employeeId: number; date: string; rect: DOMRect; current: Status }

export default function StatusMenu({ target, title, onPick, onClose }: {
  target: MenuTarget; title: string; onPick: (s: Status) => void; onClose: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    ref.current?.querySelector<HTMLButtonElement>('button')?.focus()
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    const click = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) onClose() }
    document.addEventListener('keydown', key)
    document.addEventListener('mousedown', click)
    return () => { document.removeEventListener('keydown', key); document.removeEventListener('mousedown', click) }
  }, [onClose])
  const left = Math.min(target.rect.left, window.innerWidth - 190)
  const top = target.rect.bottom + 4 + 210 > window.innerHeight ? target.rect.top - 214 : target.rect.bottom + 4
  return (
    <div ref={ref} role="menu" aria-label={title} className="status-menu card" style={{ left, top }}>
      <p className="menu-title">{title}</p>
      {STATUS_ORDER.map((s) => (
        <button key={s} role="menuitemradio" aria-checked={s === target.current} className={s === target.current ? 'current' : ''}
          onClick={() => onPick(s)}>
          <span className={`abbr st-${s}`}>{STATUS_META[s].abbr}</span> {STATUS_META[s].label}
        </button>
      ))}
    </div>
  )
}
