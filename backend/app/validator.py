"""Independent roster validator: checks any roster (solver output or manual edits)."""
from __future__ import annotations

from datetime import date

from app.calendar_rules import month_days, required_staff
from app.domain import ERROR, WARNING, WORK, Entry, Issue, ProcessCfg, Snapshot

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _pn(p: ProcessCfg) -> str:
    return p.label or p.name


def _fmt(d: date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def windows_overlap(a: ProcessCfg, b: ProcessCfg) -> bool:
    """True only when both processes have explicit shift windows that overlap. 'General' never overlaps."""
    if None in (a.shift_start, a.shift_end, b.shift_start, b.shift_end):
        return False

    def span(p: ProcessCfg) -> tuple[int, int]:
        s = p.shift_start.hour * 60 + p.shift_start.minute
        e = p.shift_end.hour * 60 + p.shift_end.minute
        return s, e if e > s else e + 1440  # overnight window

    (s1, e1), (s2, e2) = span(a), span(b)
    return s1 < e2 and s2 < e1


def validate(snap: Snapshot, entries: list[Entry]) -> list[Issue]:
    days = month_days(snap.year, snap.month)
    day_set = set(days)
    emp_by_id = {e.id: e for e in snap.employees}
    proc_by_id = {p.id: p for p in snap.processes}

    # status[(employee, date)]; entries for unknown employees or dates outside the month are ignored
    status = {(e.employee_id, e.date): e.status for e in entries
              if e.employee_id in emp_by_id and e.date in day_set}

    def works(eid: int, d: date) -> bool:
        return status.get((eid, d)) == WORK

    # backup cover: a WORK entry tagged with the process it covers counts toward that process only
    cover: dict[tuple[int, date], set[int]] = {}
    for e in entries:
        if e.cover_process_id is not None and e.status == WORK and e.employee_id in emp_by_id and e.date in day_set:
            cover.setdefault((e.cover_process_id, e.date), set()).add(e.employee_id)

    assigned: dict[int, list[int]] = {p.id: [] for p in snap.processes}
    procs_of: dict[int, list[int]] = {e.id: [] for e in snap.employees}
    for a in snap.assignments:
        if a.role == "primary" and a.process_id in assigned and a.employee_id in emp_by_id:
            assigned[a.process_id].append(a.employee_id)
            procs_of[a.employee_id].append(a.process_id)

    issues: list[Issue] = []

    # --- coverage (hard) and thin coverage (soft) ---
    for p in snap.processes:
        staff = assigned[p.id]
        for d in days:
            req = required_staff(p, d, snap.holidays)
            if req == 0:
                continue
            working = sum(1 for eid in staff if works(eid, d)) + len(cover.get((p.id, d), set()) - set(staff))
            if working == 0:
                if not staff:
                    why = "no employee is assigned to this process"
                else:
                    off = ", ".join(emp_by_id[e].name for e in staff)
                    why = f"all assigned employees ({off}) are off or on leave"
                issues.append(Issue(ERROR, "NO_COVERAGE",
                                    f"{_pn(p)} needs {req} on {_fmt(d)} but nobody is working: {why}. "
                                    f"Assign a backup or move a day off.", d, p.id))
            elif working < req:
                issues.append(Issue(ERROR, "UNDERSTAFFED",
                                    f"{_pn(p)} needs {req} on {_fmt(d)} but only {working} working. "
                                    f"Add {req - working} more.", d, p.id))
            elif working == req and req >= 2:
                issues.append(Issue(WARNING, "THIN_COVERAGE",
                                    f"{_pn(p)} has exactly the minimum {req} on {_fmt(d)}; no spare if someone drops out.",
                                    d, p.id))

    # --- per-employee rules ---
    work_on_sun_hol: dict[int, int] = {}
    for emp in snap.employees:
        leave_days = snap.leaves.get(emp.id, frozenset())
        streak = 0
        off_days = 0
        for d in days:
            w = works(emp.id, d)
            if w and d in leave_days:
                issues.append(Issue(ERROR, "WORK_ON_LEAVE",
                                    f"{emp.name} is scheduled to work on {_fmt(d)} but has approved leave.",
                                    d, None, emp.id))
            if w:
                streak += 1
                if streak == snap.params.max_consecutive + 1:
                    issues.append(Issue(ERROR, "REST_RULE",
                                        f"{emp.name} works more than {snap.params.max_consecutive} days in a row "
                                        f"(reaching {_fmt(d)}). Give a day off.", d, None, emp.id))
                if d.weekday() == 6 or d in snap.holidays:
                    work_on_sun_hol[emp.id] = work_on_sun_hol.get(emp.id, 0) + 1
                if emp.preferred_off_weekday is not None and d.weekday() == emp.preferred_off_weekday:
                    issues.append(Issue(WARNING, "PREF_OFF_VIOLATED",
                                        f"{emp.name} prefers {WEEKDAYS[d.weekday()]} off but works {_fmt(d)}.",
                                        d, None, emp.id))
                if emp.weekly_off_mode == "fixed" and emp.fixed_weekday is not None \
                        and d.weekday() == emp.fixed_weekday:
                    issues.append(Issue(WARNING, "FIXED_OFF_VIOLATED",
                                        f"{emp.name}'s fixed weekly off is {WEEKDAYS[d.weekday()]} but they work {_fmt(d)}.",
                                        d, None, emp.id))
                # incompatible shifts: two assigned processes, both operating today, with overlapping windows
                mine = [proc_by_id[pid] for pid in procs_of[emp.id]
                        if required_staff(proc_by_id[pid], d, snap.holidays) > 0]
                clash = next(((a, b) for i, a in enumerate(mine) for b in mine[i + 1:]
                              if windows_overlap(a, b)), None)
                if clash:
                    issues.append(Issue(ERROR, "SHIFT_OVERLAP",
                                        f"{emp.name} is assigned to {_pn(clash[0])} and {_pn(clash[1])} whose shift "
                                        f"windows overlap on {_fmt(d)}. Reassign one of them.", d, clash[0].id, emp.id))
            else:
                streak = 0
                off_days += 1
        if off_days < snap.params.min_off_days:
            issues.append(Issue(ERROR, "MIN_OFF_DAYS",
                                f"{emp.name} has only {off_days} days off this month "
                                f"(minimum {snap.params.min_off_days}).", None, None, emp.id))

    # --- fairness (soft): Sunday/holiday work compared with the team average ---
    staffed = [e.id for e in snap.employees if procs_of[e.id]]
    if staffed:
        avg = sum(work_on_sun_hol.get(e, 0) for e in staffed) / len(staffed)
        for eid in staffed:
            n = work_on_sun_hol.get(eid, 0)
            if n - avg >= 2:
                issues.append(Issue(WARNING, "UNFAIR_HOLIDAY_WORK",
                                    f"{emp_by_id[eid].name} works {n} Sundays/holidays, team average is {avg:.1f}.",
                                    None, None, eid))

    issues.sort(key=lambda i: (i.date or date.max, i.code, i.process_id or 0, i.employee_id or 0))
    return issues
