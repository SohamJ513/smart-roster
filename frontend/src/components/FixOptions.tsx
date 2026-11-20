import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../api'
import type { Delta, Issue, Suggestion } from '../types'

const KIND: Record<Suggestion['kind'], string> = { backup: 'Backup cover', swap: 'Swap a day off', resolve: 'Re-plan nearby days' }
export const isGap = (i: Issue) => (i.code === 'NO_COVERAGE' || i.code === 'UNDERSTAFFED') && i.date !== null && i.process_id !== null

export default function FixOptions({ rid, issue, onApplied }: { rid: number; issue: Issue; onApplied: (d: Delta) => void }) {
  const q = useQuery({
    queryKey: ['fix', rid, issue.code, issue.date, issue.process_id],
    queryFn: () => api.suggestions(rid, { date: issue.date!, process_id: issue.process_id!, code: issue.code }),
  })
  const apply = useMutation({ mutationFn: (s: Suggestion) => api.applySuggestion(rid, s.entry_changes), onSuccess: onApplied })

  if (q.isLoading) return <p className="muted pad">Looking for fixes…</p>
  if (q.isError) return <p className="alert">{(q.error as Error).message}</p>
  const list = q.data ?? []
  return (
    <div className="fixes" aria-label="Fix options">
      {list.length === 0 && (
        <p className="muted pad">No automatic fix found. Add a backup assignment for this process or change the requirement for that day.</p>
      )}
      {list.map((s, n) => (
        <div key={n} className="fix">
          <div>
            <span className="badge neutral">{KIND[s.kind]}</span>{' '}
            <span className={`badge ${s.resolves ? 'good' : 'warn'}`}>{s.resolves ? 'Fixes this gap' : 'Helps, gap remains'}</span>
            <p>{s.description}</p>
          </div>
          <button className="primary" disabled={apply.isPending} onClick={() => apply.mutate(s)}>Apply this fix</button>
        </div>
      ))}
      {apply.isError && <p className="alert">{(apply.error as Error).message}</p>}
    </div>
  )
}
