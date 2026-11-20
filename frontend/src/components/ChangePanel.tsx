import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api'
import { shortDate } from '../lib/dates'
import type { RosterData } from '../hooks/useRosterData'
import type { Delta, Issue, LeaveItem, WhatIf } from '../types'
import FixOptions, { isGap } from './FixOptions'

function range(from: string, to: string): string[] {
  const out: string[] = []
  for (let d = new Date(`${from}T00:00:00Z`); d <= new Date(`${to}T00:00:00Z`) && out.length < 31; d.setUTCDate(d.getUTCDate() + 1)) {
    out.push(d.toISOString().slice(0, 10))
  }
  return out
}

export default function ChangePanel({ rid, data, onApplied, onClose }: {
  rid: number; data: RosterData; onApplied: (d: Delta) => void; onClose: () => void
}) {
  const first = data.days[0], last = data.days[data.days.length - 1]
  const [employeeId, setEmployeeId] = useState<number>(data.employees[0]?.id ?? 0)
  const [from, setFrom] = useState(first)
  const [to, setTo] = useState(first)
  const [type, setType] = useState<'planned' | 'comp_off'>('planned')
  const [preview, setPreview] = useState<WhatIf | null>(null)
  const [applied, setApplied] = useState<Delta | null>(null)

  const leaves: LeaveItem[] = range(from, to).map((date) => ({ employee_id: employeeId, date, type }))
  const check = useMutation({ mutationFn: () => api.impact(rid, leaves), onSuccess: (r) => { setPreview(r); setApplied(null) } })
  const apply = useMutation({
    mutationFn: () => api.applyLeave(rid, leaves),
    onSuccess: (d) => { setApplied(d); setPreview(null); onApplied(d) },
  })
  const err = (check.error ?? apply.error) as Error | null
  const errorsOf = (l: Issue[]) => l.filter((i) => i.severity === 'ERROR')
  const gaps = applied ? applied.new_issues.filter(isGap) : []

  return (
    <div className="card panel" aria-label="Add leave">
      <div className="panel-head">
        <h2>Add leave and see the impact</h2>
        <button onClick={onClose}>Close</button>
      </div>
      <p className="muted">Check what a leave would break before you apply it. Nothing changes until you apply.</p>
      <form className="grid" onSubmit={(e) => { e.preventDefault(); check.mutate() }}>
        <div className="field"><label htmlFor="lv-emp">Employee</label>
          <select id="lv-emp" value={employeeId} onChange={(e) => { setEmployeeId(Number(e.target.value)); setPreview(null) }}>
            {data.employees.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select></div>
        <div className="field"><label htmlFor="lv-from">From</label>
          <input id="lv-from" type="date" min={first} max={last} value={from} required
            onChange={(e) => { setFrom(e.target.value); if (e.target.value > to) setTo(e.target.value); setPreview(null) }} /></div>
        <div className="field"><label htmlFor="lv-to">To</label>
          <input id="lv-to" type="date" min={from} max={last} value={to} required onChange={(e) => { setTo(e.target.value); setPreview(null) }} /></div>
        <div className="field"><label htmlFor="lv-type">Type</label>
          <select id="lv-type" value={type} onChange={(e) => setType(e.target.value as 'planned' | 'comp_off')}>
            <option value="planned">Planned leave</option><option value="comp_off">Comp-off</option>
          </select></div>
        <div className="actions"><button type="submit" className="primary" disabled={check.isPending}>{check.isPending ? 'Checking…' : 'Check impact'}</button></div>
      </form>
      {err && <p role="alert" className="alert">{err.message}</p>}

      {preview && (
        <div className="preview">
          <p><b>{errorsOf(preview.before).length} errors now → {errorsOf(preview.after).length} errors after this leave.</b></p>
          {preview.new_issues.length === 0 && <p className="good-text">No new problems. The remaining team still covers every required day.</p>}
          <ul className="plain">
            {preview.new_issues.map((i, n) => (
              <li key={n}><span className={`badge ${i.severity === 'ERROR' ? 'bad' : 'warn'}`}>{i.severity === 'ERROR' ? 'Error' : 'Warning'}</span>{' '}
                {i.date && <b>{shortDate(i.date)} </b>}{i.message}</li>
            ))}
          </ul>
          <div className="actions">
            <button className="primary" disabled={apply.isPending} onClick={() => apply.mutate()}>
              {apply.isPending ? 'Applying…' : `Apply ${leaves.length} day${leaves.length > 1 ? 's' : ''} of leave`}
            </button>
          </div>
        </div>
      )}

      {applied && (
        <div className="preview">
          <p><b>Leave applied.</b> {gaps.length ? `${gaps.length} coverage gap${gaps.length > 1 ? 's' : ''} need attention:` : 'No new coverage gaps.'}</p>
          {gaps.map((g, n) => (
            <div key={n} className="gap">
              <p><span className="badge bad">Error</span> <b>{shortDate(g.date!)}</b> {g.message}</p>
              <FixOptions rid={rid} issue={g} onApplied={(d) => { onApplied(d); setApplied({ ...d, new_issues: d.issues.filter((i) => gaps.some((x) => x.code === i.code && x.date === i.date && x.process_id === i.process_id)) }) }} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
