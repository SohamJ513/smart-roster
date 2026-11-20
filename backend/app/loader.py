"""Database rows -> pure Snapshot for the scheduling core."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app.calendar_rules import month_days
from app.domain import (AssignmentCfg, EmployeeCfg, Params, ProcessCfg, Snapshot)


def load_snapshot(session: Session, year: int, month: int) -> Snapshot:
    days = month_days(year, month)
    first, last = days[0], days[-1]

    employees = [EmployeeCfg(e.id, e.name, e.pod_id, e.weekly_off_mode, e.fixed_weekday, e.preferred_off_weekday)
                 for e in session.scalars(select(m.Employee).where(m.Employee.active).order_by(m.Employee.id))]
    active = {e.id for e in employees}

    by_weekday: dict[int, dict[int, int]] = defaultdict(dict)
    by_date: dict[int, dict[date, int]] = defaultdict(dict)
    for o in session.scalars(select(m.CoverageOverride)):
        if o.date is not None:
            by_date[o.process_id][o.date] = o.min_staff
        elif o.weekday is not None:
            by_weekday[o.process_id][o.weekday] = o.min_staff

    brand_names = {b.id: b.name for b in session.scalars(select(m.Brand))}
    processes = [ProcessCfg(p.id, p.brand_id, p.name, frozenset(p.weekdays), p.holidays_off, p.min_staff,
                            dict(by_weekday[p.id]), dict(by_date[p.id]), p.shift_start, p.shift_end,
                            f"{brand_names.get(p.brand_id, '?')} · {p.name}")
                 for p in session.scalars(select(m.Process).order_by(m.Process.id))]

    assignments = [AssignmentCfg(a.employee_id, a.process_id, a.role)
                   for a in session.scalars(select(m.Assignment).order_by(m.Assignment.id))
                   if a.employee_id in active]

    holidays = frozenset(session.scalars(select(m.Holiday.date)))

    leaves: dict[int, set[date]] = defaultdict(set)
    comp: dict[int, set[date]] = defaultdict(set)
    for lv in session.scalars(select(m.Leave).where(m.Leave.date >= first, m.Leave.date <= last)):
        if lv.employee_id in active and lv.status == "approved":
            leaves[lv.employee_id].add(lv.date)
            if lv.type == "comp_off":
                comp[lv.employee_id].add(lv.date)

    return Snapshot(year, month, employees, processes, assignments, holidays,
                    {k: frozenset(v) for k, v in leaves.items()}, Params(),
                    {k: frozenset(v) for k, v in comp.items()})
