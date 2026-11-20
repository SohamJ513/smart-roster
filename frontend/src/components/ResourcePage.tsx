import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { WEEKDAYS, type Field, type ResourceSpec, type Source } from '../resources'
import type { Brand, Employee, Pod, Process } from '../types'

type Row = { id: number } & Record<string, unknown>
const PRESETS: [string, number[]][] = [['Mon–Sat', [0, 1, 2, 3, 4, 5]], ['Mon–Fri', [0, 1, 2, 3, 4]], ['Every day', [0, 1, 2, 3, 4, 5, 6]]]

export function useLookups() {
  const pods = useQuery({ queryKey: ['list', 'pods'], queryFn: () => api.list<Pod>('pods') })
  const brands = useQuery({ queryKey: ['list', 'brands'], queryFn: () => api.list<Brand>('brands') })
  const employees = useQuery({ queryKey: ['list', 'employees'], queryFn: () => api.list<Employee>('employees') })
  const processes = useQuery({ queryKey: ['list', 'processes'], queryFn: () => api.list<Process>('processes') })
  const brandName = new Map((brands.data ?? []).map((b) => [b.id, b.name]))
  const labels: Record<Source, Map<number, string>> = {
    pods: new Map((pods.data ?? []).map((p) => [p.id, p.name])),
    brands: brandName,
    employees: new Map((employees.data ?? []).map((e) => [e.id, e.name])),
    processes: new Map((processes.data ?? []).map((p) => [p.id, `${brandName.get(p.brand_id) ?? '?'} · ${p.name}`])),
  }
  return labels
}

function show(f: Field, v: unknown, labels: Record<Source, Map<number, string>>): string {
  if (v === null || v === undefined || v === '') return '—'
  if (f.kind === 'checkbox') return v ? 'Yes' : 'No'
  if (f.kind === 'weekdays') return (v as number[]).map((d) => WEEKDAYS[d]).join(' ')
  if (f.kind === 'weekday') return WEEKDAYS[v as number]
  if (f.kind === 'time') return String(v).slice(0, 5)
  if (f.kind === 'select') {
    if (f.source) return labels[f.source].get(v as number) ?? String(v)
    return f.choices?.find((c) => c.value === v)?.label ?? String(v)
  }
  return String(v)
}

function initial(spec: ResourceSpec, row: Row | null): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const f of spec.fields) {
    out[f.key] = row ? row[f.key] ?? '' : f.default ?? (f.kind === 'checkbox' ? false : f.kind === 'weekdays' ? [] : '')
  }
  return out
}

function toPayload(spec: ResourceSpec, values: Record<string, unknown>) {
  const out: Record<string, unknown> = {}
  for (const f of spec.fields) {
    const v = values[f.key]
    const empty = v === '' || v === undefined || v === null
    if (f.kind === 'number' || f.kind === 'weekday' || (f.kind === 'select' && f.source)) out[f.key] = empty ? null : Number(v)
    else if (f.kind === 'time' || f.kind === 'date') out[f.key] = empty ? null : v
    else out[f.key] = v
  }
  return out
}

function FieldInput({ f, value, onChange, labels }: {
  f: Field; value: unknown; onChange: (v: unknown) => void; labels: Record<Source, Map<number, string>>
}) {
  const id = `f-${f.key}`
  if (f.kind === 'checkbox') {
    return (
      <label className="check"><input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} /> {f.label}</label>
    )
  }
  return (
    <div className="field">
      <label htmlFor={id}>{f.label}{f.optional ? ' (optional)' : ''}</label>
      {f.kind === 'weekdays' ? (
        <div id={id} className="weekdays">
          {WEEKDAYS.map((d, i) => {
            const on = (value as number[]).includes(i)
            return (
              <label key={d} className={`chip ${on ? 'on' : ''}`}>
                <input type="checkbox" checked={on}
                  onChange={() => onChange(on ? (value as number[]).filter((x) => x !== i) : [...(value as number[]), i].sort())} />
                {d}
              </label>
            )
          })}
          <span className="presets">
            {PRESETS.map(([name, days]) => <button type="button" key={name} className="link" onClick={() => onChange(days)}>{name}</button>)}
          </span>
        </div>
      ) : f.kind === 'select' || f.kind === 'weekday' ? (
        <select id={id} value={String(value ?? '')} onChange={(e) => onChange(e.target.value)}>
          {(f.optional || value === '') && <option value="">— none —</option>}
          {f.kind === 'weekday' && WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
          {f.source && [...labels[f.source].entries()].map(([k, name]) => <option key={k} value={k}>{name}</option>)}
          {f.choices?.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      ) : (
        <input id={id} type={f.kind === 'number' ? 'number' : f.kind} value={String(value ?? '')} min={f.kind === 'number' ? 0 : undefined}
          onChange={(e) => onChange(e.target.value)} required={!f.optional} />
      )}
      {f.help && <small>{f.help}</small>}
    </div>
  )
}

export default function ResourcePage({ spec }: { spec: ResourceSpec }) {
  const qc = useQueryClient()
  const labels = useLookups()
  const items = useQuery({ queryKey: ['list', spec.path], queryFn: () => api.list<Row>(spec.path) })
  const [editing, setEditing] = useState<Row | 'new' | null>(null)
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [error, setError] = useState<string | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)

  const refresh = () => qc.invalidateQueries({ queryKey: ['list'] })
  const save = useMutation({
    mutationFn: () => {
      const body = toPayload(spec, values)
      return editing === 'new' || editing === null ? api.create(spec.path, body) : api.update(spec.path, editing.id, body)
    },
    onSuccess: () => { setEditing(null); setError(null); refresh() },
    onError: (e: Error) => setError(e.message),
  })
  const remove = useMutation({
    mutationFn: (id: number) => api.remove(spec.path, id),
    onSuccess: () => { setConfirmId(null); refresh() },
    onError: (e: Error) => { setConfirmId(null); setError(e.message) },
  })

  const open = (row: Row | null) => { setEditing(row ?? 'new'); setValues(initial(spec, row)); setError(null) }

  return (
    <section>
      <header className="page-head">
        <div><h1>{spec.title}</h1><p className="muted">{spec.blurb}</p></div>
        <button className="primary" onClick={() => open(null)}>Add {spec.singular}</button>
      </header>
      {error && <p role="alert" className="alert">{error}</p>}
      {editing && (
        <form className="card form" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
          <h2>{editing === 'new' ? `Add ${spec.singular}` : `Edit ${spec.singular}`}</h2>
          <div className="grid">
            {spec.fields.map((f) => (
              <FieldInput key={f.key} f={f} value={values[f.key]} labels={labels}
                onChange={(v) => setValues((s) => ({ ...s, [f.key]: v }))} />
            ))}
          </div>
          <div className="actions">
            <button className="primary" type="submit" disabled={save.isPending}>{save.isPending ? 'Saving…' : `Save ${spec.singular}`}</button>
            <button type="button" onClick={() => setEditing(null)}>Cancel</button>
          </div>
        </form>
      )}
      <div className="card table-wrap">
        <table>
          <thead><tr>{spec.fields.map((f) => <th key={f.key}>{f.label}</th>)}<th /></tr></thead>
          <tbody>
            {(items.data ?? []).map((row) => (
              <tr key={row.id}>
                {spec.fields.map((f) => <td key={f.key}>{show(f, row[f.key], labels)}</td>)}
                <td className="row-actions">
                  <button onClick={() => open(row)}>Edit</button>
                  {confirmId === row.id
                    ? <button className="danger" onClick={() => remove.mutate(row.id)}>Delete {spec.singular}?</button>
                    : <button onClick={() => setConfirmId(row.id)}>Delete</button>}
                </td>
              </tr>
            ))}
            {items.data?.length === 0 && (
              <tr><td colSpan={spec.fields.length + 1} className="muted">No {spec.title.toLowerCase()} yet. Add the first one.</td></tr>
            )}
          </tbody>
        </table>
        {items.isLoading && <p className="muted pad">Loading…</p>}
      </div>
    </section>
  )
}
