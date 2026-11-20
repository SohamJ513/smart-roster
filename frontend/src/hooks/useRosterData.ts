import { useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { monthDays } from '../lib/dates'
import type { Assignment, Brand, Coverage, Employee, Entry, Holiday, Issue, Pod, Process, RosterDetail } from '../types'

export interface RosterData {
  ready: boolean
  roster?: RosterDetail
  days: string[]
  pods: Pod[]; brands: Brand[]; employees: Employee[]; processes: Process[]; assignments: Assignment[]
  holidays: Map<string, string>
  issues: Issue[]
  coverage: Coverage[]
  entry: (employeeId: number, date: string) => Entry | undefined
  cover: (processId: number, date: string) => Coverage | undefined
  issueDates: Map<string, Issue[]>          // "employeeId|date" -> issues on that person-day
  employeeName: (id: number) => string
  processLabel: (id: number) => string
  refresh: () => void
}

export function useRosterData(id: number): RosterData {
  const qc = useQueryClient()
  const roster = useQuery({ queryKey: ['roster', id], queryFn: () => api.getRoster(id) })
  const issues = useQuery({ queryKey: ['issues', id], queryFn: () => api.validateRoster(id) })
  const coverage = useQuery({ queryKey: ['coverage', id], queryFn: () => api.coverage(id) })
  const pods = useQuery({ queryKey: ['list', 'pods'], queryFn: () => api.list<Pod>('pods') })
  const brands = useQuery({ queryKey: ['list', 'brands'], queryFn: () => api.list<Brand>('brands') })
  const employees = useQuery({ queryKey: ['list', 'employees'], queryFn: () => api.list<Employee>('employees') })
  const processes = useQuery({ queryKey: ['list', 'processes'], queryFn: () => api.list<Process>('processes') })
  const assignments = useQuery({ queryKey: ['list', 'assignments'], queryFn: () => api.list<Assignment>('assignments') })
  const holidays = useQuery({ queryKey: ['list', 'holidays'], queryFn: () => api.list<Holiday>('holidays') })

  return useMemo(() => {
    const entries = new Map((roster.data?.entries ?? []).map((e) => [`${e.employee_id}|${e.date}`, e]))
    const cov = new Map((coverage.data ?? []).map((c) => [`${c.process_id}|${c.date}`, c]))
    const issueDates = new Map<string, Issue[]>()
    for (const i of issues.data ?? []) {
      if (i.employee_id !== null && i.date) {
        const k = `${i.employee_id}|${i.date}`
        issueDates.set(k, [...(issueDates.get(k) ?? []), i])
      }
    }
    const brandName = new Map((brands.data ?? []).map((b) => [b.id, b.name]))
    const procs = processes.data ?? []
    const emps = employees.data ?? []
    const ready = [roster, issues, coverage, pods, brands, employees, processes, assignments, holidays].every((q) => q.isSuccess)
    return {
      ready,
      roster: roster.data,
      days: roster.data ? monthDays(roster.data.year, roster.data.month) : [],
      pods: pods.data ?? [], brands: brands.data ?? [], employees: emps, processes: procs,
      assignments: assignments.data ?? [],
      holidays: new Map((holidays.data ?? []).map((h) => [h.date, h.name])),
      issues: issues.data ?? [],
      coverage: coverage.data ?? [],
      entry: (e: number, d: string) => entries.get(`${e}|${d}`),
      cover: (p: number, d: string) => cov.get(`${p}|${d}`),
      issueDates,
      employeeName: (eid: number) => emps.find((x) => x.id === eid)?.name ?? `#${eid}`,
      processLabel: (pid: number) => {
        const p = procs.find((x) => x.id === pid)
        return p ? `${brandName.get(p.brand_id) ?? '?'} · ${p.name}` : `#${pid}`
      },
      refresh: () => {
        for (const k of ['roster', 'issues', 'coverage']) qc.invalidateQueries({ queryKey: [k, id] })
      },
    }
  }, [roster.data, issues.data, coverage.data, pods.data, brands.data, employees.data, processes.data, assignments.data, holidays.data,
      roster.isSuccess, issues.isSuccess, coverage.isSuccess, pods.isSuccess, brands.isSuccess, employees.isSuccess,
      processes.isSuccess, assignments.isSuccess, holidays.isSuccess, qc, id])
}