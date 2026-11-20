import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import CoverageTable from '../components/CoverageTable'
import EmployeeCalendar from '../components/EmployeeCalendar'
import ChangePanel from '../components/ChangePanel'
import IssuesPanel from '../components/IssuesPanel'
import ChangeResult from '../components/ChangeResult'
import SummaryStrip from '../components/SummaryStrip'
import PublishPanel from '../components/PublishPanel'
import RosterGrid, { type GridGroup } from '../components/RosterGrid'
import { useRosterData } from '../hooks/useRosterData'
import { monthLabel } from '../lib/dates'
import { STATUS_META, STATUS_ORDER } from '../lib/status'
import type { Delta, Employee, Issue, Status } from '../types'

type View = 'company' | 'pod' | 'brand' | 'process' | 'employee'
const VIEWS: [View, string][] = [['company', 'Company'], ['pod', 'Pod'], ['brand', 'Brand'], ['process', 'Process'], ['employee', 'Employee']]

export default function RosterPage() {
  const rid = Number(useParams().id)
  const data = useRosterData(rid)
  const [sp, setSp] = useSearchParams()
  const view = (sp.get('view') ?? 'company') as View
  const date = sp.get('date')
  const qc = useQueryClient()
  const [result, setResult] = useState<{ delta: Delta; errorsBefore: number } | null>(null)
  const [panel, setPanel] = useState<'leave' | 'publish' | null>(null)
  const [notice, setNotice] = useState<{ text: string; tone: 'bad' | 'good' | 'neutral' } | null>(null)
  useEffect(() => { if (!notice) return; const t = setTimeout(() => setNotice(null), 7000); return () => clearTimeout(t) }, [notice])

  const patch = useMutation({
    mutationFn: (v: { employeeId: number; date: string; status: Status }) =>
      api.patchEntry(rid, { employee_id: v.employeeId, date: v.date, status: v.status, cover_process_id: null }),
    onSuccess: (d: Delta) => {
      data.refresh()
      const wasPublished = data.roster?.status === 'published'
      const errs = d.new_issues.filter((i) => i.severity === 'ERROR')
      if (errs.length) setNotice({ tone: 'bad', text: `${errs.length} new error${errs.length > 1 ? 's' : ''}: ${errs[0].message}` })
      else if (d.resolved_issues.length) setNotice({ tone: 'good', text: `Saved. ${d.resolved_issues.length} problem${d.resolved_issues.length > 1 ? 's' : ''} resolved.` })
      else setNotice({ tone: 'neutral', text: 'Saved. No new errors.' })
      if (wasPublished) setNotice({ tone: 'neutral', text: 'Saved. This roster was published, so it is a draft again; publish it once you are happy.' })
    },
    onError: (e: Error) => setNotice({ tone: 'bad', text: e.message }),
  })

  const applied = (d: Delta) => {
    const errorsNow = data.issues.filter((i) => i.severity === 'ERROR').length
    setResult({ delta: d, errorsBefore: errorsNow })
    data.refresh()
    qc.removeQueries({ queryKey: ['fix', rid] })
  }

  if (!data.ready || !data.roster) return <section><p className="muted">Loading roster…</p></section>
  const roster = data.roster

  const options: { id: number; label: string }[] =
    view === 'pod' ? data.pods.map((p) => ({ id: p.id, label: `${p.name} pod` }))
    : view === 'brand' ? data.brands.map((b) => ({ id: b.id, label: b.name }))
    : view === 'process' ? data.processes.map((p) => ({ id: p.id, label: data.processLabel(p.id) }))
    : view === 'employee' ? data.employees.map((e) => ({ id: e.id, label: e.name }))
    : []
  const target = Number(sp.get('target')) || options[0]?.id

  const go = (v: View, t?: number, d?: string | null) => {
    const next = new URLSearchParams()
    next.set('view', v)
    if (t) next.set('target', String(t))
    if (d) next.set('date', d)
    setSp(next)
  }
  const jump = (i: Issue) => {
    if (i.process_id !== null) go('process', i.process_id, i.date)
    else if (i.employee_id !== null) go('employee', i.employee_id, i.date)
  }
  const onChange = (employeeId: number, d: string, status: Status) => patch.mutate({ employeeId, date: d, status })

  const podGroup = (podId: number): GridGroup => {
    const pod = data.pods.find((p) => p.id === podId)!
    const lead = data.employees.find((e) => e.id === pod.lead_employee_id)
    const members = data.employees.filter((e) => e.pod_id === podId)
      .sort((a, b) => Number(b.id === lead?.id) - Number(a.id === lead?.id))
    return { title: `${pod.name} pod${lead ? ` · lead: ${lead.name}` : ''}`,
             rows: members.map((e) => ({ employee: e, sub: e.id === lead?.id ? 'Pod lead' : undefined })) }
  }
  const staffRows = (processIds: number[]) => {
    const rows = new Map<number, { employee: Employee; held: string[] }>()
    const add = (e: Employee | undefined, label: string) => {
      if (!e) return
      const r = rows.get(e.id) ?? { employee: e, held: [] }
      if (label && !r.held.includes(label)) r.held.push(label)
      rows.set(e.id, r)
    }
    for (const a of data.assignments.filter((x) => processIds.includes(x.process_id))) {
      add(data.employees.find((e) => e.id === a.employee_id), `${data.processes.find((p) => p.id === a.process_id)?.name}${a.role === 'backup' ? ' (backup)' : ''}`)
    }
    for (const pid of processIds) for (const d of data.days) {
      for (const eid of data.cover(pid, d)?.employee_ids ?? []) {
        if (!rows.has(eid)) add(data.employees.find((e) => e.id === eid), 'cover')
      }
    }
    return [...rows.values()].map((r) => ({ employee: r.employee, sub: r.held.join(' · ') }))
  }

  let body
  if (view === 'company') {
    body = <RosterGrid data={data} groups={data.pods.map((p) => podGroup(p.id))} highlightDate={date} onChange={onChange} errorStrip />
  } else if (view === 'pod' && target) {
    body = <RosterGrid data={data} groups={[podGroup(target)]} highlightDate={date} onChange={onChange} errorStrip />
  } else if (view === 'brand' && target) {
    const pids = data.processes.filter((p) => p.brand_id === target).map((p) => p.id)
    body = <>
      <CoverageTable data={data} processIds={pids} highlightDate={date} />
      <RosterGrid data={data} groups={[{ rows: staffRows(pids) }]} highlightDate={date} onChange={onChange} />
    </>
  } else if (view === 'process' && target) {
    const p = data.processes.find((x) => x.id === target)
    body = <>
      {p && <p className="rule card pad">
        <b>{data.processLabel(p.id)}</b> · operates {p.weekdays.map((d) => ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d]).join(', ')}
        {p.holidays_off ? ', closed on public holidays' : ', open on public holidays'} · needs {p.min_staff} per day
        {p.shift_start && ` · ${p.shift_label} shift ${p.shift_start.slice(0, 5)}–${p.shift_end?.slice(0, 5)}`}
      </p>}
      <CoverageTable data={data} processIds={[target]} highlightDate={date} />
      <RosterGrid data={data} groups={[{ rows: staffRows([target]) }]} highlightDate={date} onChange={onChange} />
    </>
  } else if (view === 'employee' && target) {
    const emp = data.employees.find((e) => e.id === target)
    body = emp ? <EmployeeCalendar data={data} employee={emp} highlightDate={date} onChange={onChange} /> : null
  }

  const errors = data.issues.filter((i) => i.severity === 'ERROR').length
  return (
    <section>
      <header className="page-head">
        <div>
          <h1>{monthLabel(roster.year, roster.month)} roster <span className={`badge ${roster.status === 'published' ? 'good' : 'neutral'}`}>{roster.status === 'published' ? 'Published' : 'Draft'}</span></h1>
          <p className="muted">
            <span className={errors ? 'bad-text' : 'good-text'}>{errors} error{errors === 1 ? '' : 's'}</span> · {data.issues.length - errors} warning{data.issues.length - errors === 1 ? '' : 's'} · click any cell to change it
          </p>
        </div>
        <div className="head-actions">
          <button onClick={() => setPanel(panel === 'leave' ? null : 'leave')}>Add leave</button>
          <button className="primary" disabled={roster.status === 'published'} onClick={() => setPanel(panel === 'publish' ? null : 'publish')}>
            {roster.status === 'published' ? 'Published' : 'Publish roster'}
          </button>
          <Link className="btn" to="/roster">All rosters</Link>
          <a className="btn" href={api.exportUrl(rid)} download>Download CSV</a>
        </div>
      </header>
      {panel === 'leave' && <ChangePanel rid={rid} data={data} onApplied={applied} onClose={() => setPanel(null)} />}
      {panel === 'publish' && <PublishPanel rid={rid} data={data} onClose={() => setPanel(null)}
        onDone={() => { setPanel(null); data.refresh(); qc.invalidateQueries({ queryKey: ['rosters'] }); setNotice({ tone: 'good', text: 'Roster published.' }) }} />}
      <SummaryStrip data={data} />
      {result && <ChangeResult delta={result.delta} errorsBefore={result.errorsBefore} onClose={() => setResult(null)} />}
      {notice && <p role="status" className={`notice ${notice.tone}`}>{notice.text}</p>}
      <div className="tabs" role="tablist">
        {VIEWS.map(([v, label]) => <button key={v} role="tab" aria-selected={view === v} className={view === v ? 'on' : ''} onClick={() => go(v)}>{label}</button>)}
        {options.length > 0 && (
          <select aria-label={`Choose ${view}`} value={target} onChange={(e) => go(view, Number(e.target.value))}>
            {options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        )}
      </div>
      <p className="status-legend" aria-label="Legend">
        {STATUS_ORDER.map((st) => (
          <span key={st}><span className={`abbr st-${st}`}>{STATUS_META[st].abbr}</span>{STATUS_META[st].label}</span>
        ))}
        <span>Underlined = edited by hand · red outline = causes an error</span>
      </p>
      <div className="roster-layout">
        <div className="main-col">{body}</div>
        <IssuesPanel rid={rid} data={data} onJump={jump} onApplied={applied} />
      </div>
    </section>
  )
}