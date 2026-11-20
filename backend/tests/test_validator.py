from copy import deepcopy
from datetime import date, time

from app.domain import ERROR, WARNING, Entry, WORK
from app.validator import validate
from tests.helpers import ALL7, D, SUNDAYS, emp, proc, replace, roster, snap


def codes(issues, severity=None):
    return [i.code for i in issues if severity is None or i.severity == severity]


def test_single_employee_on_leave_gives_no_coverage_error():
    s = snap([emp(1)], [proc(1)], [(1, 1)], leaves={1: {D(10)}})
    issues = validate(s, roster([1], leave_days={1: {10}}))
    errors = [i for i in issues if i.severity == ERROR]
    assert len(errors) == 1
    assert errors[0].code == "NO_COVERAGE" and errors[0].date == D(10) and errors[0].process_id == 1


def test_two_needed_one_working_is_understaffed():
    s = snap([emp(1), emp(2)], [proc(1, min_staff=2)], [(1, 1), (2, 1)])
    entries = replace(roster([1, 2]), 2, 9, "WEEKLY_OFF")
    errors = [i for i in validate(s, entries) if i.severity == ERROR]
    assert [(i.code, i.date) for i in errors] == [("UNDERSTAFFED", D(9))]


def test_three_assigned_one_off_still_covered_no_error():
    s = snap([emp(1), emp(2), emp(3)], [proc(1, min_staff=2)], [(1, 1), (2, 1), (3, 1)])
    entries = replace(roster([1, 2, 3]), 3, 9, "WEEKLY_OFF")
    issues = validate(s, entries)
    assert codes(issues, ERROR) == []
    assert "THIN_COVERAGE" in codes(issues, WARNING)  # exactly at the minimum of 2


def test_work_on_leave_is_error():
    s = snap([emp(1)], [], [], leaves={1: {D(10)}})
    issues = validate(s, roster([1]))  # entry says WORK on a leave day
    hit = [i for i in issues if i.code == "WORK_ON_LEAVE"]
    assert len(hit) == 1 and hit[0].severity == ERROR and hit[0].employee_id == 1 and hit[0].date == D(10)


def test_seven_work_days_in_a_row_is_rest_error():
    s = snap([emp(1)])
    entries = roster([1], off_days={8, 15, 22, 29})  # Dec 1-7 is a 7-day streak
    hit = [i for i in validate(s, entries) if i.code == "REST_RULE"]
    assert len(hit) == 1 and hit[0].date == D(7) and hit[0].severity == ERROR


def test_six_in_a_row_is_fine():
    s = snap([emp(1)])
    assert "REST_RULE" not in codes(validate(s, roster([1], off_days={7, 14, 21, 28})))


def test_too_few_off_days_is_error():
    s = snap([emp(1)])
    entries = roster([1], off_days={7, 14, 21})  # only 3 non-working days
    assert "MIN_OFF_DAYS" in codes(validate(s, entries), ERROR)


def test_overlapping_explicit_shifts_same_day_is_shift_overlap():
    procs = [proc(1, brand=1, weekdays=ALL7, start=time(9), end=time(17)),
             proc(2, brand=2, weekdays=ALL7, start=time(14), end=time(22))]
    s = snap([emp(1)], procs, [(1, 1), (1, 2)])
    issues = validate(s, roster([1]))
    assert any(i.code == "SHIFT_OVERLAP" and i.severity == ERROR and i.employee_id == 1 for i in issues)


def test_adjacent_shift_windows_do_not_overlap():
    procs = [proc(1, brand=1, weekdays=ALL7, start=time(6), end=time(14)),
             proc(2, brand=2, weekdays=ALL7, start=time(14), end=time(22))]
    s = snap([emp(1)], procs, [(1, 1), (1, 2)])
    assert "SHIFT_OVERLAP" not in codes(validate(s, roster([1])))


def test_general_processes_never_overlap():
    procs = [proc(1, brand=1, weekdays=ALL7), proc(2, brand=1, weekdays=ALL7)]
    s = snap([emp(1)], procs, [(1, 1), (1, 2)])
    assert "SHIFT_OVERLAP" not in codes(validate(s, roster([1])))


def test_preferred_off_violated_is_warning_not_error():
    s = snap([emp(1, preferred_off_weekday=2)])  # Wednesday; roster has them working Wednesdays
    hits = [i for i in validate(s, roster([1])) if i.code == "PREF_OFF_VIOLATED"]
    assert hits and all(i.severity == WARNING and i.employee_id == 1 for i in hits)


def test_fixed_off_violated_is_warning():
    s = snap([emp(1, weekly_off_mode="fixed", fixed_weekday=2)])
    hits = [i for i in validate(s, roster([1])) if i.code == "FIXED_OFF_VIOLATED"]
    assert hits and all(i.severity == WARNING for i in hits)


def test_process_with_no_assignments_gives_no_coverage_every_operating_day():
    s = snap([emp(1)], [proc(1, weekdays=ALL7)], [])
    hits = [i for i in validate(s, roster([1])) if i.code == "NO_COVERAGE"]
    assert len(hits) == 31 and {i.date for i in hits} == {D(d) for d in range(1, 32)}


def test_employee_with_no_assignments_causes_no_issue():
    s = snap([emp(1)])
    assert validate(s, roster([1])) == []


def test_entries_outside_month_or_unknown_employee_ignored():
    s = snap([emp(1)])
    base = roster([1])
    extra = base + [Entry(999, D(5), WORK), Entry(1, date(2027, 1, 5), WORK)]
    assert validate(s, extra) == validate(s, base)


def test_validator_does_not_mutate_inputs():
    s = snap([emp(1)], [proc(1)], [(1, 1)], leaves={1: {D(10)}})
    entries = roster([1], leave_days={1: {10}})
    s0, e0 = deepcopy(s), deepcopy(entries)
    validate(s, entries)
    assert s == s0 and entries == e0


def test_backup_cover_entry_counts_toward_the_process_it_covers():
    s = snap([emp(1), emp(2)], [proc(1)], [(1, 1)], leaves={1: {D(10)}})   # e2 is not assigned to P1
    entries = roster([1], leave_days={1: {10}}) + roster([2], off_days=SUNDAYS | {10})
    assert any(i.code == "NO_COVERAGE" and i.date == D(10) for i in validate(s, entries))
    covered = [Entry(e.employee_id, e.date, WORK, True, "manual", cover_process_id=1)
               if (e.employee_id, e.date) == (2, D(10)) else e for e in entries]
    assert not any(i.code == "NO_COVERAGE" and i.date == D(10) for i in validate(s, covered))


def test_messages_name_the_brand_when_the_process_has_a_label():
    s = snap([emp(1)], [proc(1, label="Glow · CS")], [(1, 1)], leaves={1: {D(10)}})
    msg = next(i.message for i in validate(s, roster([1], leave_days={1: {10}})) if i.code == "NO_COVERAGE")
    assert "Glow · CS" in msg
