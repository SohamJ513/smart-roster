export type Status = 'WORK' | 'WEEKLY_OFF' | 'HOLIDAY' | 'LEAVE' | 'COMP_OFF'
export type Severity = 'ERROR' | 'WARNING'

export interface Issue {
  severity: Severity
  code: string
  message: string
  date: string | null
  process_id: number | null
  employee_id: number | null
}

export interface Entry {
  employee_id: number
  date: string
  status: Status
  cover_process_id: number | null
  locked: boolean
  source: string
}

export interface EntryChange {
  employee_id: number
  date: string
  status: Status
  cover_process_id: number | null
}

export interface Pod { id: number; name: string; lead_employee_id: number | null }
export interface Employee {
  id: number; name: string; pod_id: number; weekly_off_mode: 'fixed' | 'flexible'
  fixed_weekday: number | null; preferred_off_weekday: number | null; active: boolean
}
export interface Brand { id: number; name: string; default_weekdays: number[]; default_holidays_off: boolean }
export interface Process {
  id: number; brand_id: number; name: string; weekdays: number[]; holidays_off: boolean
  min_staff: number; shift_label: string; shift_start: string | null; shift_end: string | null
}
export interface Assignment { id: number; employee_id: number; process_id: number; role: 'primary' | 'backup' }
export interface Holiday { id: number; date: string; name: string }
export interface Leave { id: number; employee_id: number; date: string; type: 'planned' | 'comp_off'; status: string }
export interface Override { id: number; process_id: number; weekday: number | null; date: string | null; min_staff: number }

export interface RosterSummary { id: number; year: number; month: number; status: 'draft' | 'published'; version: number }
export interface RosterDetail extends RosterSummary { acknowledged_codes: string[]; entries: Entry[] }
export interface Delta { issues: Issue[]; new_issues: Issue[]; resolved_issues: Issue[] }
export interface WhatIf { before: Issue[]; after: Issue[]; new_issues: Issue[]; resolved_issues: Issue[] }
export interface Suggestion { kind: 'backup' | 'swap' | 'resolve'; description: string; resolves: boolean; entry_changes: EntryChange[] }
export interface LeaveItem { employee_id: number; date: string; type: 'planned' | 'comp_off' }

export interface Coverage { process_id: number; date: string; required: number; working: number; employee_ids: number[] }
