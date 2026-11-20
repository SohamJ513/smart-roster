"""Tiny builders shared by core tests. December 2026: Dec 1 is a Tuesday; Sundays are 6, 13, 20, 27."""
from datetime import date

from app.calendar_rules import month_days
from app.domain import (AssignmentCfg, Entry, EmployeeCfg, Params, ProcessCfg, Snapshot,
                        WORK, WEEKLY_OFF, LEAVE)

Y, M = 2026, 12
SUNDAYS = {6, 13, 20, 27}
MON_SAT = frozenset(range(6))
ALL7 = frozenset(range(7))


def D(day: int) -> date:
    return date(Y, M, day)


def proc(pid=1, brand=1, weekdays=MON_SAT, holidays_off=False, min_staff=1, start=None, end=None, label="", **kw):
    return ProcessCfg(id=pid, brand_id=brand, name=f"P{pid}", weekdays=weekdays, holidays_off=holidays_off,
                      min_staff=min_staff, shift_start=start, shift_end=end, label=label, **kw)


def emp(eid, pod=1, **kw):
    return EmployeeCfg(id=eid, name=f"E{eid}", pod_id=pod, **kw)


def snap(employees, processes=(), assignments=(), holidays=(), leaves=None, params=None):
    return Snapshot(year=Y, month=M, employees=list(employees), processes=list(processes),
                    assignments=[AssignmentCfg(e, p) for e, p in assignments],
                    holidays=frozenset(holidays), leaves={k: frozenset(v) for k, v in (leaves or {}).items()},
                    params=params or Params())


def roster(emp_ids, off_days=SUNDAYS, leave_days=None):
    """WORK every day except off_days (WEEKLY_OFF); leave_days = {emp_id: {day,...}} become LEAVE."""
    leave_days = leave_days or {}
    out = []
    for e in emp_ids:
        for d in month_days(Y, M):
            if d.day in leave_days.get(e, set()):
                out.append(Entry(e, d, LEAVE))
            elif d.day in off_days:
                out.append(Entry(e, d, WEEKLY_OFF))
            else:
                out.append(Entry(e, d, WORK))
    return out


def replace(entries, emp_id, day, status):
    return [Entry(e.employee_id, e.date, status, e.locked, e.source) if (e.employee_id == emp_id and e.date == D(day)) else e
            for e in entries]
