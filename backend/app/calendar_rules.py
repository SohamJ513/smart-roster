"""Operating calendar: when a process needs coverage and how many people."""
from __future__ import annotations

import calendar
from datetime import date

from app.domain import ProcessCfg


def month_days(year: int, month: int) -> list[date]:
    n = calendar.monthrange(year, month)[1]
    return [date(year, month, d) for d in range(1, n + 1)]


def is_operating(p: ProcessCfg, d: date, holidays: frozenset[date]) -> bool:
    if d.weekday() not in p.weekdays:
        return False
    if p.holidays_off and d in holidays:
        return False
    return True


def required_staff(p: ProcessCfg, d: date, holidays: frozenset[date]) -> int:
    """0 when closed; date override beats weekday override beats min_staff."""
    if not is_operating(p, d, holidays):
        return 0
    if d in p.overrides_by_date:
        return p.overrides_by_date[d]
    if d.weekday() in p.overrides_by_weekday:
        return p.overrides_by_weekday[d.weekday()]
    return p.min_staff
