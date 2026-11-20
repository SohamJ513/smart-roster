import { useState } from 'react'
import { dayNumber, weekdayIndex } from '../lib/dates'
import { STATUS_META } from '../lib/status'
import type { RosterData } from '../hooks/useRosterData'
import type { Employee, Status } from '../types'
import StatusMenu, { type MenuTarget } from './StatusMenu'

export default function EmployeeCalendar({ data, employee, highlightDate, onChange }: {
  data: RosterData; employee: Employee; highlightDate: string | null
  onChange: (employeeId: number, date: string, status: Status) => void
}) {
  const [menu, setMenu] = useState<MenuTarget | null>(null)
  const lead = weekdayIndex(data.days[0])
  const mine = data.assignments.filter((a) => a.employee_id === employee.id)
  const counts: Record<string, number> = {}
  for (const d of data.days) { const s = data.entry(employee.id, d)?.status ?? 'WEEKLY_OFF'; counts[s] = (counts[s] ?? 0) + 1 }
  return (
    <div className="card cal">
      <div className="cal-head">
        <div>
          <h2>{employee.name}</h2>
          <p className="muted">
            {data.pods.find((p) => p.id === employee.pod_id)?.name ?? 'No'} pod · weekly off: {employee.weekly_off_mode}
          </p>
          <p className="muted">Works on: {mine.length ? mine.map((a) => `${data.processLabel(a.process_id)}${a.role === 'backup' ? ' (backup)' : ''}`).join(', ') : 'nothing assigned'}</p>
        </div>
        <ul className="tally">
          {Object.entries(STATUS_META).map(([k, m]) => <li key={k}><span className={`abbr st-${k}`}>{m.abbr}</span> {m.label}: <b>{counts[k] ?? 0}</b></li>)}
        </ul>
      </div>
      <div className="cal-grid" role="grid">
        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => <div key={d} className="cal-dow">{d}</div>)}
        {Array.from({ length: lead }, (_, i) => <div key={`pad${i}`} />)}
        {data.days.map((d) => {
          const e = data.entry(employee.id, d)
          const status: Status = e?.status ?? 'WEEKLY_OFF'
          const hol = data.holidays.get(d)
          const issues = data.issueDates.get(`${employee.id}|${d}`) ?? []
          return (
            <button key={d} className={`cal-day st-${status} ${highlightDate === d ? 'hl' : ''} ${issues.length ? 'err' : ''}`}
              title={issues.map((i) => i.message).join(' ')}
              onClick={(ev) => setMenu({ employeeId: employee.id, date: d, rect: ev.currentTarget.getBoundingClientRect(), current: status })}>
              <b>{dayNumber(d)}</b><span>{STATUS_META[status].label}</span>
              {hol && <small>{hol}</small>}
              {e?.cover_process_id && <small>covering {data.processLabel(e.cover_process_id)}</small>}
            </button>
          )
        })}
      </div>
      {menu && (
        <StatusMenu target={menu} title={`${employee.name} · ${menu.date}`} onClose={() => setMenu(null)}
          onPick={(s) => { onChange(menu.employeeId, menu.date, s); setMenu(null) }} />
      )}
    </div>
  )
}
