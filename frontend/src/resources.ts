export type FieldKind = 'text' | 'number' | 'checkbox' | 'select' | 'weekdays' | 'weekday' | 'date' | 'time'
export type Source = 'pods' | 'brands' | 'employees' | 'processes'

export interface Field {
  key: string
  label: string
  kind: FieldKind
  source?: Source          // for select fields backed by another resource
  choices?: { value: string; label: string }[]  // for select fields with fixed choices
  optional?: boolean
  default?: unknown
  help?: string
}

export interface ResourceSpec {
  path: string
  title: string
  singular: string
  blurb: string
  fields: Field[]
}

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export const RESOURCES: ResourceSpec[] = [
  {
    path: 'pods', title: 'Pods', singular: 'pod', blurb: 'Operational groups, each overseen by a pod lead.',
    fields: [
      { key: 'name', label: 'Pod name', kind: 'text' },
      { key: 'lead_employee_id', label: 'Pod lead', kind: 'select', source: 'employees', optional: true },
    ],
  },
  {
    path: 'employees', title: 'Employees', singular: 'employee', blurb: 'Everyone who appears on the roster.',
    fields: [
      { key: 'name', label: 'Name', kind: 'text' },
      { key: 'pod_id', label: 'Pod', kind: 'select', source: 'pods' },
      { key: 'weekly_off_mode', label: 'Weekly off', kind: 'select', default: 'flexible',
        choices: [{ value: 'flexible', label: 'Flexible (solver picks)' }, { value: 'fixed', label: 'Fixed weekday' }] },
      { key: 'fixed_weekday', label: 'Fixed off weekday', kind: 'weekday', optional: true, help: 'Only used when weekly off is fixed.' },
      { key: 'preferred_off_weekday', label: 'Preferred off weekday', kind: 'weekday', optional: true,
        help: 'A preference only: required coverage wins over it.' },
      { key: 'active', label: 'Active', kind: 'checkbox', default: true },
    ],
  },
  {
    path: 'brands', title: 'Brands', singular: 'brand', blurb: 'Client brands. Each has processes with their own rules.',
    fields: [
      { key: 'name', label: 'Brand name', kind: 'text' },
      { key: 'default_weekdays', label: 'Default operating days', kind: 'weekdays', default: [0, 1, 2, 3, 4, 5] },
      { key: 'default_holidays_off', label: 'Closed on public holidays by default', kind: 'checkbox', default: true },
    ],
  },
  {
    path: 'processes', title: 'Processes', singular: 'process', blurb: 'Work types per brand, with the days they must be covered.',
    fields: [
      { key: 'brand_id', label: 'Brand', kind: 'select', source: 'brands' },
      { key: 'name', label: 'Process name', kind: 'text', help: 'For example CS, ACC, NDR, Retention.' },
      { key: 'weekdays', label: 'Operating days', kind: 'weekdays', default: [0, 1, 2, 3, 4, 5] },
      { key: 'holidays_off', label: 'Closed on public holidays', kind: 'checkbox', default: true },
      { key: 'min_staff', label: 'Minimum people per day', kind: 'number', default: 1 },
      { key: 'shift_label', label: 'Shift label', kind: 'text', default: 'General', help: 'General has no time window.' },
      { key: 'shift_start', label: 'Shift start', kind: 'time', optional: true },
      { key: 'shift_end', label: 'Shift end', kind: 'time', optional: true },
    ],
  },
  {
    path: 'assignments', title: 'Assignments', singular: 'assignment', blurb: 'Who works on which process. Primary staff count toward coverage.',
    fields: [
      { key: 'employee_id', label: 'Employee', kind: 'select', source: 'employees' },
      { key: 'process_id', label: 'Process', kind: 'select', source: 'processes' },
      { key: 'role', label: 'Role', kind: 'select', default: 'primary',
        choices: [{ value: 'primary', label: 'Primary' }, { value: 'backup', label: 'Backup' }] },
    ],
  },
  {
    path: 'overrides', title: 'Coverage overrides', singular: 'override', blurb: 'Different minimum staffing on a weekday or a specific date.',
    fields: [
      { key: 'process_id', label: 'Process', kind: 'select', source: 'processes' },
      { key: 'weekday', label: 'Weekday', kind: 'weekday', optional: true, help: 'Set a weekday or a date, not both.' },
      { key: 'date', label: 'Date', kind: 'date', optional: true },
      { key: 'min_staff', label: 'Minimum people', kind: 'number', default: 2 },
    ],
  },
  {
    path: 'holidays', title: 'Public holidays', singular: 'holiday', blurb: 'One shared calendar for all brands.',
    fields: [
      { key: 'date', label: 'Date', kind: 'date' },
      { key: 'name', label: 'Holiday name', kind: 'text' },
    ],
  },
  {
    path: 'leaves', title: 'Leaves and comp-offs', singular: 'leave', blurb: 'Approved days an employee cannot work.',
    fields: [
      { key: 'employee_id', label: 'Employee', kind: 'select', source: 'employees' },
      { key: 'date', label: 'Date', kind: 'date' },
      { key: 'type', label: 'Type', kind: 'select', default: 'planned',
        choices: [{ value: 'planned', label: 'Planned leave' }, { value: 'comp_off', label: 'Comp-off' }] },
    ],
  },
]
