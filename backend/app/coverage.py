"""Per-process, per-day coverage numbers shared by the API and the views (one source of truth)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.calendar_rules import month_days, required_staff
from app.domain import WORK, Entry, Snapshot


@dataclass(frozen=True)
class CoverageCell:
    process_id: int
    date: date
    required: int
    working: int
    employee_ids: list[int]


def coverage_grid(snap: Snapshot, entries: list[Entry]) -> list[CoverageCell]:
    days = month_days(snap.year, snap.month)
    day_set = set(days)
    working = {(e.employee_id, e.date) for e in entries if e.status == WORK and e.date in day_set}
    covers: dict[tuple[int, date], set[int]] = {}
    for e in entries:
        if e.status == WORK and e.cover_process_id is not None and e.date in day_set:
            covers.setdefault((e.cover_process_id, e.date), set()).add(e.employee_id)
    primary: dict[int, list[int]] = {p.id: [] for p in snap.processes}
    for a in snap.assignments:
        if a.role == "primary" and a.process_id in primary:
            primary[a.process_id].append(a.employee_id)

    grid: list[CoverageCell] = []
    for p in snap.processes:
        for d in days:
            staff = {eid for eid in primary[p.id] if (eid, d) in working} | covers.get((p.id, d), set())
            grid.append(CoverageCell(p.id, d, required_staff(p, d, snap.holidays), len(staff), sorted(staff)))
    return grid
