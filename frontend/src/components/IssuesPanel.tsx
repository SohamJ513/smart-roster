import { useState } from 'react'
import { shortDate } from '../lib/dates'
import { groupIssues } from '../lib/summary'
import type { RosterData } from '../hooks/useRosterData'
import type { Delta, Issue } from '../types'
import FixOptions, { isGap } from './FixOptions'

type Filter = 'ALL' | 'ERROR' | 'WARNING'
const keyOf = (i: Issue) => `${i.code}|${i.date}|${i.process_id}|${i.employee_id}`

export default function IssuesPanel({ rid, data, onJump, onApplied }: {
  rid: number; data: RosterData; onJump: (i: Issue) => void; onApplied: (d: Delta) => void
}) {
  const [picked, setFilter] = useState<Filter | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const errors = data.issues.filter((i) => i.severity === 'ERROR').length
  const warnings = data.issues.length - errors
  const filter: Filter = picked ?? (errors > 0 ? 'ERROR' : 'ALL')   // errors first when there are any
  const groups = groupIssues(data.issues.filter((i) => filter === 'ALL' || i.severity === filter))
  // Errors are always listed; warning groups start collapsed so a long list stays readable.
  const isOpen = (g: { code: string; severity: string }) => expanded[g.code] ?? g.severity === 'ERROR'
  return (
    <aside className="card issues" aria-label="Roster problems">
      <header>
        <h2>Problems</h2>
        <div className="seg" role="group" aria-label="Filter problems">
          <button className={filter === 'ALL' ? 'on' : ''} onClick={() => setFilter('ALL')}>All {data.issues.length}</button>
          <button className={filter === 'ERROR' ? 'on' : ''} onClick={() => setFilter('ERROR')}>Errors {errors}</button>
          <button className={filter === 'WARNING' ? 'on' : ''} onClick={() => setFilter('WARNING')}>Warnings {warnings}</button>
        </div>
      </header>
      {data.issues.length === 0 && <p className="muted pad">No problems. Every required day is covered.</p>}
      {data.issues.length > 0 && groups.length === 0 && <p className="muted pad">Nothing in this filter.</p>}
      {groups.map((g) => (
        <section key={g.code} className="issue-group">
          <button className="group-head" aria-expanded={isOpen(g)} onClick={() => setExpanded({ ...expanded, [g.code]: !isOpen(g) })}>
            <span className={`badge ${g.severity === 'ERROR' ? 'bad' : 'warn'}`}>{g.issues.length}</span>
            <span className="group-title">{g.title}</span>
            <span className="chev" aria-hidden>{isOpen(g) ? '▾' : '▸'}</span>
          </button>
          {isOpen(g) && (
            <ul>
              {g.issues.map((i) => (
                <li key={keyOf(i)}>
                  <button onClick={() => onJump(i)}>
                    {i.date && <span className="when">{shortDate(i.date)}</span>}
                    <span className="msg">{i.message}</span>
                  </button>
                  {isGap(i) && (
                    <div className="fix-toggle">
                      <button className="link" aria-expanded={open === keyOf(i)} onClick={() => setOpen(open === keyOf(i) ? null : keyOf(i))}>
                        {open === keyOf(i) ? 'Hide fix options' : 'Find fix options'}
                      </button>
                      {open === keyOf(i) && <FixOptions rid={rid} issue={i} onApplied={(d) => { setOpen(null); onApplied(d) }} />}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </aside>
  )
}