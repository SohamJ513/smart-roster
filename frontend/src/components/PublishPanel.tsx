import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api'
import type { RosterData } from '../hooks/useRosterData'

export default function PublishPanel({ rid, data, onDone, onClose }: {
  rid: number; data: RosterData; onDone: () => void; onClose: () => void
}) {
  const errors = data.issues.filter((i) => i.severity === 'ERROR')
  const byCode = new Map<string, number>()
  for (const e of errors) byCode.set(e.code, (byCode.get(e.code) ?? 0) + 1)
  const [ack, setAck] = useState(false)
  const publish = useMutation({ mutationFn: () => api.publish(rid, [...byCode.keys()]), onSuccess: onDone })
  return (
    <div className="card panel" aria-label="Publish roster">
      <div className="panel-head"><h2>Publish this roster</h2><button onClick={onClose}>Cancel</button></div>
      {errors.length === 0 ? (
        <p className="good-text">No errors. Every required day is covered and no hard rule is broken.</p>
      ) : (
        <>
          <p className="alert">{errors.length} error{errors.length > 1 ? 's' : ''} are still unresolved:
            {' '}{[...byCode.entries()].map(([c, n]) => `${c.replaceAll('_', ' ').toLowerCase()} (${n})`).join(', ')}.</p>
          <label className="check"><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
            I know about these errors and want to publish anyway.</label>
        </>
      )}
      {publish.isError && <p role="alert" className="alert">{(publish.error as Error).message}</p>}
      <div className="actions">
        <button className="primary" disabled={publish.isPending || (errors.length > 0 && !ack)} onClick={() => publish.mutate()}>
          {publish.isPending ? 'Publishing…' : 'Publish roster'}
        </button>
      </div>
    </div>
  )
}
