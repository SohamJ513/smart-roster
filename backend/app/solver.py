"""Roster generation with OR-Tools CP-SAT.

Coverage, rest and minimum-off rules use slack variables with large penalties, so the solver always
returns a roster plus the validator's list of what is still wrong, never a bare "infeasible".
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ortools.sat.python import cp_model

from app.calendar_rules import month_days, required_staff
from app.domain import (COMP_OFF, HOLIDAY, LEAVE, WEEKLY_OFF, WORK, Entry, Issue, Snapshot)
from app.validator import validate, windows_overlap

# Penalty weights: coverage gaps are reported rather than hidden; rest rules rank above coverage
# (a gap is shown to the manager, a breach of the rest rule is not allowed to be traded for it).
W_REST = 100_000
W_OFF = 100_000
W_SHORT = 10_000
W_FIXED = 50
W_PREF = 10
W_FAIR = 5
W_THIN = 2


@dataclass(frozen=True)
class SolveResult:
    entries: list[Entry]
    issues: list[Issue]


def _fixed_entries(locked: list[Entry], window: tuple[date, date] | None,
                   emp_ids: set[int], days: set[date]) -> dict[tuple[int, date], Entry]:
    """An entry in `locked` is fixed when there is no window, it lies outside the window,
    or it carries locked=True inside the window."""
    out: dict[tuple[int, date], Entry] = {}
    for e in locked:
        if e.employee_id not in emp_ids or e.date not in days:
            continue
        inside = window is not None and window[0] <= e.date <= window[1]
        if window is None or not inside or e.locked:
            out[(e.employee_id, e.date)] = e
    return out


def generate(snap: Snapshot, locked: list[Entry] | None = None,
             window: tuple[date, date] | None = None, time_limit_s: float = 10.0) -> SolveResult:
    days = month_days(snap.year, snap.month)
    day_set = set(days)
    emp_ids = {e.id for e in snap.employees}
    fixed = _fixed_entries(locked or [], window, emp_ids, day_set)

    primary: dict[int, list[int]] = {p.id: [] for p in snap.processes}
    procs_of: dict[int, list[int]] = {e.id: [] for e in snap.employees}
    for a in snap.assignments:
        if a.role == "primary" and a.process_id in primary and a.employee_id in emp_ids:
            primary[a.process_id].append(a.employee_id)
            procs_of[a.employee_id].append(a.process_id)
    proc_by_id = {p.id: p for p in snap.processes}

    m = cp_model.CpModel()
    work = {(e.id, d): m.NewBoolVar(f"w_{e.id}_{d.day}") for e in snap.employees for d in days}

    # --- fixed values: locked entries first, then leave, then shift clashes ---
    forced: dict[tuple[int, date], int] = {}
    for key, entry in fixed.items():
        forced[key] = 1 if entry.status == WORK else 0
    for e in snap.employees:
        for d in snap.leaves.get(e.id, frozenset()):
            if d in day_set:
                forced.setdefault((e.id, d), 0)
        pids = procs_of[e.id]
        for i, p in enumerate(pids):
            for q in pids[i + 1:]:
                if windows_overlap(proc_by_id[p], proc_by_id[q]):
                    for d in days:
                        if (required_staff(proc_by_id[p], d, snap.holidays) > 0
                                and required_staff(proc_by_id[q], d, snap.holidays) > 0):
                            forced.setdefault((e.id, d), 0)
    for key, val in forced.items():
        m.Add(work[key] == val)

    penalties: list = []

    # fixed backup-cover entries count as constants toward the process they cover
    fixed_cover: dict[tuple[int, date], int] = {}
    for (eid, d), entry in fixed.items():
        if entry.cover_process_id is not None and entry.status == WORK \
                and eid not in primary.get(entry.cover_process_id, []):
            fixed_cover[(entry.cover_process_id, d)] = fixed_cover.get((entry.cover_process_id, d), 0) + 1

    # --- coverage with slack ---
    for p in snap.processes:
        for d in days:
            req = required_staff(p, d, snap.holidays)
            if req == 0:
                continue
            total = sum(work[(eid, d)] for eid in primary[p.id]) + fixed_cover.get((p.id, d), 0)
            slack = m.NewIntVar(0, req, f"s_{p.id}_{d.day}")
            m.Add(total + slack >= req)
            penalties.append(W_SHORT * slack)
            if req >= 2:  # soft: prefer one spare person above the minimum
                spare = m.NewBoolVar(f"sp_{p.id}_{d.day}")
                m.Add(total + slack - req >= spare)
                penalties.append(W_THIN * (1 - spare))

    # --- rest rule and minimum days off, as heavily penalised slack ---
    k = snap.params.max_consecutive
    for e in snap.employees:
        for start in range(0, len(days) - k):
            window_vars = [work[(e.id, days[i])] for i in range(start, start + k + 1)]
            over = m.NewIntVar(0, 1, f"r_{e.id}_{start}")
            m.Add(sum(window_vars) <= k + over)
            penalties.append(W_REST * over)
        need_off = min(snap.params.min_off_days, len(days))
        short = m.NewIntVar(0, need_off, f"o_{e.id}")
        m.Add(sum(work[(e.id, d)] for d in days) <= len(days) - need_off + short)
        penalties.append(W_OFF * short)

    # --- soft preferences ---
    for e in snap.employees:
        for d in days:
            if e.preferred_off_weekday is not None and d.weekday() == e.preferred_off_weekday:
                penalties.append(W_PREF * work[(e.id, d)])
            if e.weekly_off_mode == "fixed" and e.fixed_weekday is not None and d.weekday() == e.fixed_weekday:
                penalties.append(W_FIXED * work[(e.id, d)])

    # --- fairness: spread Sunday/holiday work across employees that have assignments ---
    staffed = [e.id for e in snap.employees if procs_of[e.id]]
    special = [d for d in days if d.weekday() == 6 or d in snap.holidays]
    if len(staffed) > 1 and special:
        counts = []
        for eid in staffed:
            c = m.NewIntVar(0, len(special), f"c_{eid}")
            m.Add(c == sum(work[(eid, d)] for d in special))
            counts.append(c)
        hi = m.NewIntVar(0, len(special), "hi")
        lo = m.NewIntVar(0, len(special), "lo")
        m.AddMaxEquality(hi, counts)
        m.AddMinEquality(lo, counts)
        penalties.append(W_FAIR * (hi - lo))

    m.Minimize(sum(penalties))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 4
    solver.parameters.random_seed = 7
    status = solver.Solve(m)
    solved = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    entries: list[Entry] = []
    for e in snap.employees:
        leave_days = snap.leaves.get(e.id, frozenset())
        comp_days = snap.comp_offs.get(e.id, frozenset())
        for d in days:
            if (e.id, d) in fixed:
                entries.append(fixed[(e.id, d)])
                continue
            if solved and solver.Value(work[(e.id, d)]):
                st = WORK
            elif d in comp_days:
                st = COMP_OFF
            elif d in leave_days:
                st = LEAVE
            elif d in snap.holidays:
                st = HOLIDAY
            else:
                st = WEEKLY_OFF
            entries.append(Entry(e.id, d, st))
    return SolveResult(entries=entries, issues=validate(snap, entries))
