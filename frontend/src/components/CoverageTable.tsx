import { coverageCell } from '../lib/coverage'
import { shortDate } from '../lib/dates'
import type { RosterData } from '../hooks/useRosterData'
import { DayHeaders } from './RosterGrid'

export default function CoverageTable({ data, processIds, highlightDate }: {
  data: RosterData; processIds: number[]; highlightDate: string | null
}) {
  return (
    <div className="card grid-wrap">
      <table className="roster-grid cover-grid">
        <thead><tr><th className="name-col">Process · working / required</th><DayHeaders data={data} highlightDate={highlightDate} /></tr></thead>
        <tbody>
          {processIds.map((pid) => (
            <tr key={pid}>
              <th className="name-col"><span>{data.processLabel(pid)}</span></th>
              {data.days.map((d) => {
                const c = data.cover(pid, d)
                const state = c ? coverageCell(c.required, c.working) : 'closed'
                const who = c ? c.employee_ids.map(data.employeeName).join(', ') || 'nobody' : ''
                const text = state === 'closed' ? 'Closed' : `${c?.working} of ${c?.required} working: ${who}`
                return (
                  <td key={d} className={highlightDate === d ? 'hl' : ''}>
                    <span className={`cov cov-${state}`} title={`${shortDate(d)} · ${text}`} aria-label={`${data.processLabel(pid)} ${shortDate(d)}: ${text}`}>
                      {state === 'closed' ? '·' : `${c?.working}/${c?.required}`}
                    </span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="legend">
        <span className="cov cov-ok">ok</span> covered · <span className="cov cov-thin">thin</span> exactly the minimum ·
        <span className="cov cov-gap"> gap</span> short · <span className="cov cov-closed">·</span> closed that day
      </p>
    </div>
  )
}
