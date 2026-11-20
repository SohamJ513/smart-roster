from app.coverage import coverage_grid
from app.domain import WORK, Entry
from tests.helpers import D, SUNDAYS, emp, proc, replace, roster, snap


def cell(grid, pid, day):
    return next(c for c in grid if c.process_id == pid and c.date == D(day))


def test_grid_has_a_cell_for_every_process_and_day_with_required_and_working():
    s = snap([emp(1), emp(2)], [proc(1, min_staff=2)], [(1, 1), (2, 1)])
    entries = replace(roster([1, 2]), 2, 9, "WEEKLY_OFF")
    grid = coverage_grid(s, entries)
    assert len(grid) == 31
    assert (cell(grid, 1, 9).required, cell(grid, 1, 9).working, cell(grid, 1, 9).employee_ids) == (2, 1, [1])
    assert cell(grid, 1, 6).required == 0           # Sunday: process closed
    assert cell(grid, 1, 8).working == 2


def test_backup_cover_entry_is_counted_and_listed():
    s = snap([emp(1), emp(2)], [proc(1)], [(1, 1)], leaves={1: {D(10)}})
    entries = roster([1], leave_days={1: {10}}) + roster([2], off_days=SUNDAYS | {10})
    entries = [Entry(e.employee_id, e.date, WORK, True, "manual", cover_process_id=1)
               if (e.employee_id, e.date) == (2, D(10)) else e for e in entries]
    c = cell(coverage_grid(s, entries), 1, 10)
    assert (c.required, c.working, c.employee_ids) == (1, 1, [2])
