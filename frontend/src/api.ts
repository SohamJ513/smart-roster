import type { Coverage, Delta, EntryChange, Issue, LeaveItem, RosterDetail, RosterSummary, Suggestion, WhatIf } from './types'

export function buildQuery(params: Record<string, string | number | undefined>): string {
  return Object.entries(params)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&')
}

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, message: string, detail: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

function describe(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`).join('; ')
  }
  if (detail && typeof detail === 'object' && 'message' in detail) return String((detail as { message: unknown }).message)
  return 'Something went wrong. Try again.'
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail: unknown = null
    try { detail = (await res.json()).detail } catch { /* not JSON */ }
    throw new ApiError(res.status, describe(detail), detail)
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

export const api = {
  list: <T>(resource: string) => request<T[]>('GET', `/api/${resource}`),
  create: <T>(resource: string, body: unknown) => request<T>('POST', `/api/${resource}`, body),
  update: <T>(resource: string, id: number, body: unknown) => request<T>('PUT', `/api/${resource}/${id}`, body),
  remove: (resource: string, id: number) => request<void>('DELETE', `/api/${resource}/${id}`),
  resetDemo: () => request<{ status: string }>('POST', '/api/demo/reset'),

  listRosters: () => request<RosterSummary[]>('GET', '/api/rosters'),
  generateRoster: (year: number, month: number) =>
    request<{ roster_id: number; issues: Issue[] }>('POST', '/api/rosters/generate', { year, month }),
  getRoster: (id: number) => request<RosterDetail>('GET', `/api/rosters/${id}`),
  coverage: (id: number) => request<Coverage[]>('GET', `/api/rosters/${id}/coverage`),
  validateRoster: (id: number) => request<Issue[]>('GET', `/api/rosters/${id}/validate`),
  patchEntry: (id: number, change: EntryChange) => request<Delta>('PATCH', `/api/rosters/${id}/entries`, change),
  impact: (id: number, leaves: LeaveItem[]) => request<WhatIf>('POST', `/api/rosters/${id}/impact`, { leaves }),
  applyLeave: (id: number, leaves: LeaveItem[]) => request<Delta>('POST', `/api/rosters/${id}/apply-leave`, { leaves }),
  suggestions: (id: number, q: { date: string; process_id: number; code: string }) =>
    request<Suggestion[]>('GET', `/api/rosters/${id}/suggestions?${buildQuery(q)}`),
  applySuggestion: (id: number, entry_changes: EntryChange[]) =>
    request<Delta>('POST', `/api/rosters/${id}/apply-suggestion`, { entry_changes }),
  publish: (id: number, codes: string[]) =>
    request<{ status: string }>('POST', `/api/rosters/${id}/publish`, { acknowledged_issue_codes: codes }),
  exportUrl: (id: number) => `/api/rosters/${id}/export.csv`,
}
