import { describe, expect, it } from 'vitest'
import { groupIssues, summarize } from './summary'
import type { Coverage, Issue } from '../types'

const issue = (code: string, severity: 'ERROR' | 'WARNING', date: string | null = '2026-12-01'): Issue =>
  ({ severity, code, message: code, date, process_id: null, employee_id: null })
const cov = (required: number, working: number): Coverage => ({ process_id: 1, date: '2026-12-01', required, working, employee_ids: [] })

describe('summarize', () => {
  it('counts errors, warnings, covered process-days and people under minimum off days', () => {
    const s = summarize(
      [issue('NO_COVERAGE', 'ERROR'), issue('MIN_OFF_DAYS', 'ERROR', null), issue('THIN_COVERAGE', 'WARNING')],
      [cov(2, 2), cov(1, 0), cov(0, 0), cov(1, 3)],
    )
    expect(s).toEqual({ errors: 2, warnings: 1, coveredDays: 2, operatingDays: 3, underMinOff: 1 })
  })
  it('handles an empty roster', () => {
    expect(summarize([], [])).toEqual({ errors: 0, warnings: 0, coveredDays: 0, operatingDays: 0, underMinOff: 0 })
  })
})

describe('groupIssues', () => {
  it('groups by code, errors first, each group keeps its issues in order', () => {
    const g = groupIssues([issue('THIN_COVERAGE', 'WARNING', '2026-12-02'), issue('NO_COVERAGE', 'ERROR'),
      issue('THIN_COVERAGE', 'WARNING', '2026-12-01')])
    expect(g.map((x) => [x.code, x.severity, x.issues.length])).toEqual([['NO_COVERAGE', 'ERROR', 1], ['THIN_COVERAGE', 'WARNING', 2]])
    expect(g[1].issues.map((i) => i.date)).toEqual(['2026-12-01', '2026-12-02'])
    expect(g[1].title).toBe('Days with no spare person')
  })
})