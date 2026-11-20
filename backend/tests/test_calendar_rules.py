from datetime import date

from app.calendar_rules import is_operating, month_days, required_staff
from app.domain import ProcessCfg

ALL = frozenset(range(7))
HOL = frozenset({date(2026, 12, 25)})  # a Friday
SUN = date(2026, 12, 6)
FRI = date(2026, 12, 11)


def proc(**kw):
    base = dict(id=1, brand_id=1, name="CS", weekdays=ALL, holidays_off=False, min_staff=1)
    base.update(kw)
    return ProcessCfg(**base)


def test_365_operates_on_sunday_and_holiday():
    p = proc()
    assert is_operating(p, SUN, HOL)
    assert is_operating(p, date(2026, 12, 25), HOL)


def test_daily_except_holidays_closed_on_holiday():
    p = proc(holidays_off=True)
    assert not is_operating(p, date(2026, 12, 25), HOL)
    assert is_operating(p, SUN, HOL)


def test_sundays_and_holidays_off_closed_on_sunday():
    p = proc(weekdays=frozenset(range(6)), holidays_off=True)
    assert not is_operating(p, SUN, HOL)
    assert is_operating(p, date(2026, 12, 7), HOL)


def test_date_override_beats_weekday_override():
    p = proc(min_staff=1, overrides_by_weekday={4: 2}, overrides_by_date={FRI: 3})
    assert required_staff(p, FRI, HOL) == 3
    assert required_staff(p, date(2026, 12, 18), HOL) == 2  # another Friday
    assert required_staff(p, date(2026, 12, 8), HOL) == 1


def test_required_staff_zero_when_closed():
    p = proc(weekdays=frozenset(range(6)), holidays_off=True, min_staff=2)
    assert required_staff(p, SUN, HOL) == 0


def test_month_days_feb_2027_has_28():
    days = month_days(2027, 2)
    assert len(days) == 28 and days[0] == date(2027, 2, 1) and days[-1] == date(2027, 2, 28)
