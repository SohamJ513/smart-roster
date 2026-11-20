import type { Delta } from '../types'
import { shortDate } from '../lib/dates'

export default function ChangeResult({ delta, errorsBefore, onClose }: { delta: Delta; errorsBefore: number; onClose: () => void }) {
  const errorsAfter = delta.issues.filter((i) => i.severity === 'ERROR').length
  const resolved = delta.resolved_issues
  const added = delta.new_issues
  return (
    <section className="card panel result" role="status" aria-label="What changed">
      <div className="panel-head">
        <h2>What changed</h2>
        <button className="link" onClick={onClose}>Dismiss</button>
      </div>
      <p className="before-after">
        Errors <b className={errorsBefore ? 'bad-text' : 'good-text'}>{errorsBefore}</b> → <b className={errorsAfter ? 'bad-text' : 'good-text'}>{errorsAfter}</b>
      </p>
      {resolved.length > 0 && <>
        <p className="muted">Resolved ({resolved.length})</p>
        <ul className="plain">{resolved.slice(0, 5).map((i, n) => <li key={n}>{i.date && <b>{shortDate(i.date)} </b>}{i.message}</li>)}</ul>
      </>}
      {added.length > 0 && <>
        <p className="muted">New ({added.length})</p>
        <ul className="plain">{added.slice(0, 5).map((i, n) => <li key={n}>{i.date && <b>{shortDate(i.date)} </b>}{i.message}</li>)}</ul>
      </>}
      {resolved.length === 0 && added.length === 0 && <p className="muted">No problems were added or resolved.</p>}
    </section>
  )
}