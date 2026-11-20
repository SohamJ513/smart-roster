import time
from datetime import date

from app.domain import (AssignmentCfg, ERROR, LEAVE, WEEKLY_OFF, WORK, Entry, Params, Snapshot)
from app.solver import generate
from tests.helpers import D, emp, proc, snap

T = 8.0  # keep tests quick


def status_map(entries):
    return {(e.employee_id, e.date): e.status for e in entries}


def errors(result):
    return [i for i in result.issues if i.severity == ERROR]


def feasible_team():
    employees = [emp(i) for i in range(1, 6)]
    procs = [proc(1, brand=1), proc(2, brand=2, min_staff=2)]
    assigns = [(1, 1), (2, 1), (3, 2), (4, 2), (5, 2)]
    return employees, procs, assigns


def test_generated_roster_has_no_errors_for_feasible_input():
    e, p, a = feasible_team()
    res = generate(snap(e, p, a), time_limit_s=T)
    assert errors(res) == []
    assert len(res.entries) == 5 * 31


def test_leave_is_never_scheduled_as_work():
    e, p, a = feasible_team()
    res = generate(snap(e, p, a, leaves={1: {D(10), D(11)}}), time_limit_s=T)
    sm = status_map(res.entries)
    assert sm[(1, D(10))] == LEAVE and sm[(1, D(11))] == LEAVE


def test_locked_entries_are_kept():
    e, p, a = feasible_team()
    lock = Entry(3, D(8), WEEKLY_OFF, locked=True, source="manual")
    res = generate(snap(e, p, a), locked=[lock], time_limit_s=T)
    kept = [x for x in res.entries if x.employee_id == 3 and x.date == D(8)]
    assert kept == [lock]


def test_only_employee_on_leave_returns_shortfall_not_exception():
    s = snap([emp(1)], [proc(1)], [(1, 1)], leaves={1: {D(10)}})
    t0 = time.time()
    res = generate(s, time_limit_s=T)
    assert time.time() - t0 < T + 5
    gaps = [i for i in res.issues if i.code == "NO_COVERAGE"]
    assert [(i.date, i.process_id) for i in gaps] == [(D(10), 1)]


def test_everyone_on_leave_same_day_still_returns():
    s = snap([emp(1), emp(2)], [proc(1)], [(1, 1), (2, 1)], leaves={1: {D(10)}, 2: {D(10)}})
    res = generate(s, time_limit_s=T)
    assert any(i.code == "NO_COVERAGE" and i.date == D(10) for i in res.issues)
    assert len(res.entries) == 2 * 31


def test_preference_honoured_when_coverage_allows():
    s = snap([emp(1, preferred_off_weekday=2), emp(2)], [proc(1)], [(1, 1), (2, 1)])
    res = generate(s, time_limit_s=T)
    sm = status_map(res.entries)
    wednesdays = [D(d) for d in (2, 9, 16, 23, 30)]
    assert all(sm[(1, d)] != WORK for d in wednesdays)
    assert errors(res) == []


def test_coverage_beats_preference():
    s = snap([emp(1, preferred_off_weekday=2)], [proc(1)], [(1, 1)])
    res = generate(s, time_limit_s=T)
    sm = status_map(res.entries)
    assert sm[(1, D(9))] == WORK
    assert errors(res) == []
    assert any(i.code == "PREF_OFF_VIOLATED" for i in res.issues)


def test_window_resolve_only_changes_inside_window():
    e, p, a = feasible_team()
    first = generate(snap(e, p, a), time_limit_s=T)
    s2 = snap(e, p, a, leaves={3: {D(15)}})
    res = generate(s2, locked=first.entries, window=(D(13), D(19)), time_limit_s=T)
    before, after = status_map(first.entries), status_map(res.entries)
    outside = [k for k in before if not (D(13) <= k[1] <= D(19))]
    assert all(before[k] == after[k] for k in outside)
    assert after[(3, D(15))] == LEAVE


def test_february_2027_28_days():
    s = Snapshot(year=2027, month=2, employees=[emp(1), emp(2)], processes=[proc(1)],
                 assignments=[AssignmentCfg(1, 1), AssignmentCfg(2, 1)],
                 holidays=frozenset(), leaves={}, params=Params())
    res = generate(s, time_limit_s=T)
    dates = {x.date for x in res.entries}
    assert len(res.entries) == 2 * 28
    assert min(dates) == date(2027, 2, 1) and max(dates) == date(2027, 2, 28)
    assert errors(res) == []
