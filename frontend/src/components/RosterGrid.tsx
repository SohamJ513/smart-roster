import { Fragment, useState } from 'react'
import { dayNumber, shortDate, weekdayIndex } from '../lib/dates'
import { STATUS_META } from '../lib/status'
import type { RosterData } from '../hooks/useRosterData'
import type { Employee, Issue, Status } from '../types'
import StatusMenu, { type MenuTarget } from './StatusMenu'

export interface GridRow { employee: Employee; sub?: string }
export interface GridGroup { title?: string; rows: GridRow[] }

const INITIALS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']

export function DayHeaders({ data, highlightDate, today, hoverDate }: { data: RosterData; highlightDate: string | null; today?: string; hoverDate?: string | null }) {
  return (
    <>
      {data.days.map((d) => {
        const wd = weekdayIndex(d)
        const hol = data.holidays.get(d)
        return (
          <th key={d} title={hol ? `${shortDate(d)} · ${hol}` : shortDate(d)}
            className={`day ${wd === 6 ? 'sun' : ''} ${hol ? 'hol' : ''} ${highlightDate === d ? 'hl' : ''} ${today === d ? 'today' : ''} ${hoverDate === d ? 'hov' : ''}`}>
            <span>{dayNumber(d)}</span><small>{INITIALS[wd]}</small>
          </th>
        )
      })}
    </>
  )
}

export default function RosterGrid({ data, groups, highlightDate, onChange, errorStrip }: {
  data: RosterData
  groups: GridGroup[]
  highlightDate: string | null
  onChange: (employeeId: number, date: string, status: Status) => void
  errorStrip?: boolean
}) {
  const [menu, setMenu] = useState<MenuTarget | null>(null)
  const [hoverDate, setHoverDate] = useState<string | null>(null)
  const today = new Date().toISOString().slice(0, 10)
  const issuesAt = (eid: number, d: string): Issue[] => data.issueDates.get(`${eid}|${d}`) ?? []

  const errorsByDate = new Map<string, number>()
  if (errorStrip) {
    for (const i of data.issues) if (i.severity === 'ERROR' && i.date) errorsByDate.set(i.date, (errorsByDate.get(i.date) ?? 0) + 1)
  }

  return (
    <div className="card grid-wrap">
      <table className="roster-grid" onMouseLeave={() => setHoverDate(null)}>
        <thead>
          <tr><th className="name-col">Employee</th><DayHeaders data={data} highlightDate={highlightDate} today={today} hoverDate={hoverDate} /></tr>
          {errorStrip && (
            <tr className="strip">
              <th className="name-col">Problems that day</th>
              {data.days.map((d) => {
                const n = errorsByDate.get(d) ?? 0
                return <td key={d} className={n ? 'bad' : 'good'} title={n ? `${n} error(s) on ${shortDate(d)}` : 'No errors'}>{n || '✓'}</td>
              })}
            </tr>
          )}
        </thead>
        <tbody>
          {groups.map((g, gi) => (
            <Fragment key={gi}>
              {g.title && <tr className="group"><th colSpan={data.days.length + 1}>{g.title}</th></tr>}
              {g.rows.map(({ employee, sub }) => (
                <tr key={employee.id}>
                  <th className="name-col"><span>{employee.name}</span>{sub && <small>{sub}</small>}</th>
                  {data.days.map((d) => {
                    const e = data.entry(employee.id, d)
                    const status = e?.status ?? 'WEEKLY_OFF'
                    const issues = issuesAt(employee.id, d)
                    const bad = issues.some((i) => i.severity === 'ERROR')
                    const label = `${employee.name}, ${shortDate(d)}: ${STATUS_META[status].label}${e?.cover_process_id ? ` (covering ${data.processLabel(e.cover_process_id)})` : ''}`
                    return (
                      <td key={d} onMouseEnter={() => setHoverDate(d)}
                          className={`${highlightDate === d ? 'hl' : ''} ${weekdayIndex(d) === 6 ? 'sun' : ''} ${hoverDate === d ? 'hov' : ''} ${today === d ? 'today' : ''}`}>
                        <button className={`cell st-${status} ${bad ? 'err' : issues.length ? 'warn' : ''} ${e?.source === 'manual' ? 'manual' : ''}`}
                          title={label + (issues.length ? ` — ${issues.map((i) => i.message).join(' ')}` : '')}
                          aria-label={label}
                          onClick={(ev) => setMenu({ employeeId: employee.id, date: d, rect: ev.currentTarget.getBoundingClientRect(), current: status })}>
                          {STATUS_META[status].abbr}{e?.cover_process_id ? '*' : ''}
                        </button>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
      {menu && (
        <StatusMenu target={menu} title={`${data.employeeName(menu.employeeId)} · ${shortDate(menu.date)}`}
          onClose={() => setMenu(null)}
          onPick={(s) => { onChange(menu.employeeId, menu.date, s); setMenu(null) }} />
      )}
    </div>
  )
}