import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { monthLabel } from '../lib/dates'

export default function RosterHome() {
  const nav = useNavigate()
  const [month, setMonth] = useState('2026-12')
  const rosters = useQuery({ queryKey: ['rosters'], queryFn: api.listRosters })
  const gen = useMutation({
    mutationFn: () => { const [y, m] = month.split('-').map(Number); return api.generateRoster(y, m) },
    onSuccess: (r) => nav(`/roster/${r.roster_id}`),
  })
  return (
    <section>
      <header className="page-head">
        <div><h1>Rosters</h1><p className="muted">Pick a month, generate a roster for the whole team, then review the problems before publishing.</p></div>
      </header>
      <form className="card form inline" onSubmit={(e) => { e.preventDefault(); gen.mutate() }}>
        <div className="field">
          <label htmlFor="month">Month</label>
          <input id="month" type="month" value={month} onChange={(e) => setMonth(e.target.value)} required />
        </div>
        <button className="primary" type="submit" disabled={gen.isPending || !month}>
          {gen.isPending ? 'Generating…' : 'Generate roster'}
        </button>
      </form>
      {gen.isPending && (
        <p className="muted" role="status">
          Building the roster and checking every rule. On the free hosting plan this can take 10 to 30 seconds, so please keep this page open.
        </p>
      )}
      {gen.isError && <p role="alert" className="alert">{(gen.error as Error).message}</p>}
      <div className="card table-wrap">
        <table>
          <thead><tr><th>Month</th><th>Status</th><th>Roster</th><th /></tr></thead>
          <tbody>
            {(rosters.data ?? []).map((r) => (
              <tr key={r.id}>
                <td>{monthLabel(r.year, r.month)}</td>
                <td><span className={`badge ${r.status === 'published' ? 'good' : 'neutral'}`}>{r.status === 'published' ? 'Published' : 'Draft'}</span></td>
                <td>#{r.id}</td>
                <td className="row-actions"><Link className="btn" to={`/roster/${r.id}`}>Open roster</Link></td>
              </tr>
            ))}
            {rosters.data?.length === 0 && <tr><td colSpan={4} className="muted">No rosters yet. Generate the first one above.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  )
}