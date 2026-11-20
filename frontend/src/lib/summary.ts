import type { Coverage, Issue, Severity } from '../types'

export const CODE_TITLE: Record<string, string> = {
  NO_COVERAGE: 'Days nobody is working',
  UNDERSTAFFED: 'Days short of the minimum',
  WORK_ON_LEAVE: 'Scheduled during leave',
  REST_RULE: 'Too many days in a row',
  MIN_OFF_DAYS: 'Too few days off',
  SHIFT_OVERLAP: 'Overlapping shifts',
  THIN_COVERAGE: 'Days with no spare person',
  PREF_OFF_VIOLATED: 'Preferred day off not given',
  FIXED_OFF_VIOLATED: 'Fixed weekly off not given',
  UNFAIR_HOLIDAY_WORK: 'Uneven Sunday/holiday work',
}

export interface Summary { errors: number; warnings: number; coveredDays: number; operatingDays: number; underMinOff: number }

export function summarize(issues: Issue[], coverage: Coverage[]): Summary {
  const errors = issues.filter((i) => i.severity === 'ERROR').length
  const operating = coverage.filter((c) => c.required > 0)
  return {
    errors,
    warnings: issues.length - errors,
    coveredDays: operating.filter((c) => c.working >= c.required).length,
    operatingDays: operating.length,
    underMinOff: issues.filter((i) => i.code === 'MIN_OFF_DAYS').length,
  }
}

export interface IssueGroup { code: string; severity: Severity; title: string; issues: Issue[] }

export function groupIssues(issues: Issue[]): IssueGroup[] {
  const byCode = new Map<string, IssueGroup>()
  for (const i of issues) {
    const g = byCode.get(i.code) ?? { code: i.code, severity: i.severity, title: CODE_TITLE[i.code] ?? i.code, issues: [] }
    g.issues.push(i)
    byCode.set(i.code, g)
  }
  const groups = [...byCode.values()]
  for (const g of groups) g.issues.sort((a, b) => (a.date ?? '9').localeCompare(b.date ?? '9'))
  return groups.sort((a, b) => (a.severity === b.severity ? b.issues.length - a.issues.length : a.severity === 'ERROR' ? -1 : 1))
}