from copy import deepcopy

from app.changes import impact, suggest
from app.domain import ERROR, WORK
from app.validator import validate
from tests.helpers import D, SUNDAYS, emp, proc, replace, roster, snap


def errors(issues):
    return [i for i in issues if i.severity == ERROR]


def key(i):
    return (i.code, i.date, i.process_id, i.employee_id)


def single_resource():
    return snap([emp(1)], [proc(1)], [(1, 1)]), roster([1])


def test_leave_of_single_resource_employee_creates_no_coverage_issue():
    s, entries = single_resource()
    res = impact(s, entries, {1: frozenset({D(10)})})
    assert errors(res.before) == []
    assert [(i.code, i.date, i.process_id) for i in errors(res.new_issues)] == [("NO_COVERAGE", D(10), 1)]


def test_one_of_three_on_leave_creates_no_issue_when_minimum_still_met():
    s = snap([emp(1), emp(2), emp(3)], [proc(1, min_staff=2)], [(1, 1), (2, 1), (3, 1)])
    res = impact(s, roster([1, 2, 3]), {3: frozenset({D(10)})})
    assert errors(res.new_issues) == []
    assert errors(res.after) == []


def test_impact_lists_new_issue_and_leaves_before_unchanged():
    s, entries = single_resource()
    s0, e0 = deepcopy(s), deepcopy(entries)
    res = impact(s, entries, {1: frozenset({D(10)})})
    assert res.before == validate(s, entries)
    assert s == s0 and entries == e0                      # inputs not mutated
    assert {key(i) for i in res.new_issues} <= {key(i) for i in res.after}
    assert res.resolved_issues == []
    assert {x.employee_id: x.status for x in res.entries_after if x.date == D(10)}[1] == "LEAVE"
    assert res.snapshot_after.leaves[1] == frozenset({D(10)})


def _backup_setup(e3_off, e2_leave=False):
    employees = [emp(1, pod=1), emp(2, pod=1), emp(3, pod=2)]
    s = snap(employees, [proc(1)], [(1, 1)])
    entries = roster([1], off_days=SUNDAYS)
    entries += roster([2], off_days=SUNDAYS | {10}, leave_days={2: {10}} if e2_leave else None)
    entries += roster([3], off_days=e3_off)
    return s, entries


def test_backup_suggestion_prefers_same_pod():
    s, entries = _backup_setup(SUNDAYS | {10})
    res = impact(s, entries, {1: frozenset({D(10)})})
    gap = next(i for i in res.new_issues if i.code == "NO_COVERAGE")
    sugg = suggest(res.snapshot_after, res.entries_after, gap)
    backups = [x for x in sugg if x.kind == "backup"]
    assert backups and backups[0].entry_changes[0].employee_id == 2     # same pod as the brand's employee
    assert backups[0].resolves


def test_backup_never_suggests_someone_on_leave_or_over_rest_limit():
    employees = [emp(1, pod=1), emp(2, pod=1), emp(3, pod=1)]
    s = snap(employees, [proc(1)], [(1, 1)], leaves={2: {10}})
    entries = roster([1]) + roster([2], leave_days={2: {10}}) + roster([3], off_days={3, 10, 17, 24, 31})
    res = impact(s, entries, {1: frozenset({D(10)})})
    gap = next(i for i in res.new_issues if i.code == "NO_COVERAGE")
    sugg = suggest(res.snapshot_after, res.entries_after, gap)
    assert not [x for x in sugg if x.kind == "backup"
                for c in x.entry_changes if c.employee_id in (2, 3) and c.date == D(10) and c.status == WORK]


def test_applying_a_resolving_suggestion_removes_the_issue():
    s, entries = _backup_setup(SUNDAYS | {10})
    res = impact(s, entries, {1: frozenset({D(10)})})
    gap = next(i for i in res.new_issues if i.code == "NO_COVERAGE")
    best = next(x for x in suggest(res.snapshot_after, res.entries_after, gap) if x.resolves)
    changes = {(c.employee_id, c.date): c for c in best.entry_changes}
    applied = [changes.get((e.employee_id, e.date), e) for e in res.entries_after]
    after = validate(res.snapshot_after, applied)
    assert key(gap) not in {key(i) for i in after}
    assert len(errors(after)) <= len(errors(res.after))


def test_swap_moves_a_weekly_off_when_an_assigned_employee_is_off():
    s = snap([emp(1), emp(2), emp(3)], [proc(1, min_staff=2)], [(1, 1), (2, 1), (3, 1)])
    entries = replace(roster([1, 2, 3]), 3, 9, "WEEKLY_OFF")     # e3 off Wed 9th: 1,2 cover
    res = impact(s, entries, {1: frozenset({D(9)})})              # now only e2 works: understaffed
    gap = next(i for i in res.new_issues if i.code == "UNDERSTAFFED")
    swaps = [x for x in suggest(res.snapshot_after, res.entries_after, gap) if x.kind == "swap"]
    assert swaps and swaps[0].resolves
    st = {(c.employee_id, c.date): c.status for c in swaps[0].entry_changes}
    assert st[(3, D(9))] == WORK and "WEEKLY_OFF" in st.values()
    applied = {(c.employee_id, c.date): c for c in swaps[0].entry_changes}
    after = validate(res.snapshot_after, [applied.get((e.employee_id, e.date), e) for e in res.entries_after])
    assert key(gap) not in {key(i) for i in after} and len(errors(after)) < len(errors(res.after))
