"""What-if analysis for roster changes and ranked suggestions for fixing coverage gaps."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

from app.calendar_rules import month_days, required_staff
from app.domain import (ERROR, HOLIDAY, LEAVE, WEEKLY_OFF, WORK, Entry, Issue, Snapshot)
from app.solver import generate
from app.validator import validate, windows_overlap

GAP_CODES = ("NO_COVERAGE", "UNDERSTAFFED")


@dataclass(frozen=True)
class ImpactResult:
    before: list[Issue]
    after: list[Issue]
    new_issues: list[Issue]
    resolved_issues: list[Issue]
    entries_after: list[Entry]
    snapshot_after: Snapshot


@dataclass(frozen=True)
class Suggestion:
    kind: str  # "backup" | "swap" | "resolve"
    description: str
    entry_changes: list[Entry]
    resolves: bool


def _key(i: Issue) -> tuple:
    return (i.code, i.date, i.process_id, i.employee_id)


def impact(snap: Snapshot, entries: list[Entry], new_leaves: dict[int, frozenset[date]]) -> ImpactResult:
    """Apply extra leave days (what-if) and compare validator output before and after. Inputs are not mutated."""
    merged = {e: set(ds) for e, ds in snap.leaves.items()}
    for eid, ds in new_leaves.items():
        merged.setdefault(eid, set()).update(ds)
    snap_after = replace(snap, leaves={e: frozenset(ds) for e, ds in merged.items()})

    in_month = set(month_days(snap.year, snap.month))
    changed = {(eid, d) for eid, ds in new_leaves.items() for d in ds if d in in_month}
    entries_after = [Entry(e.employee_id, e.date, LEAVE, False, "manual")
                     if (e.employee_id, e.date) in changed else e for e in entries]

    before = validate(snap, entries)
    after = validate(snap_after, entries_after)
    before_keys, after_keys = {_key(i) for i in before}, {_key(i) for i in after}
    return ImpactResult(before, after,
                        [i for i in after if _key(i) not in before_keys],
                        [i for i in before if _key(i) not in after_keys],
                        entries_after, snap_after)


def suggest(snap: Snapshot, entries: list[Entry], issue: Issue) -> list[Suggestion]:
    """Ranked fixes for a coverage gap: backups (same pod first), weekly-off swaps, a partial re-solve."""
    if issue.code not in GAP_CODES or issue.date is None or issue.process_id is None:
        return []
    proc_by_id = {p.id: p for p in snap.processes}
    emp_by_id = {e.id: e for e in snap.employees}
    proc = proc_by_id.get(issue.process_id)
    if proc is None:
        return []
    d = issue.date
    status = {(e.employee_id, e.date): e.status for e in entries}
    base_issues = validate(snap, entries)
    base_error_keys = {_key(i) for i in base_issues if i.severity == ERROR}
    gap_key = _key(issue)

    def evaluate(changes: list[Entry]) -> tuple[bool, bool]:
        """(fixes the gap, introduces no new ERROR)."""
        by = {(c.employee_id, c.date): c for c in changes}
        after = validate(snap, [by.get((e.employee_id, e.date), e) for e in entries])
        err = {_key(i) for i in after if i.severity == ERROR}
        return gap_key not in err, err <= base_error_keys

    primary = {a.employee_id for a in snap.assignments if a.process_id == proc.id and a.role == "primary"}
    related = {a.employee_id for a in snap.assignments if a.process_id == proc.id}
    primary_pods = {emp_by_id[e].pod_id for e in primary if e in emp_by_id}
    workload = {}
    for (eid, _), st in status.items():
        if st == WORK:
            workload[eid] = workload.get(eid, 0) + 1

    # --- backups: anyone not already on the process who is free (off, not on leave) that day ---
    backups: list[tuple[tuple, Suggestion]] = []
    for e in snap.employees:
        if e.id in primary or status.get((e.id, d)) not in (WEEKLY_OFF, HOLIDAY) or d in snap.leaves.get(e.id, ()):
            continue
        if any(a.employee_id == e.id and a.role == "primary" and a.process_id in proc_by_id
               and windows_overlap(proc, proc_by_id[a.process_id])
               and required_staff(proc_by_id[a.process_id], d, snap.holidays) > 0 for a in snap.assignments):
            continue
        change = [Entry(e.id, d, WORK, True, "manual", cover_process_id=proc.id)]
        resolves, clean = evaluate(change)
        if not clean:
            continue
        same_pod = e.pod_id in primary_pods
        rank = (0 if resolves else 1, 0 if same_pod else 1, 0 if e.id in related else 1, workload.get(e.id, 0), e.id)
        text = (f"Ask {e.name} ({'same pod' if same_pod else 'other pod'}) to cover {proc.label or proc.name} on {d.day} {d.strftime('%b')}: "
                f"they are off that day and have {workload.get(e.id, 0)} working days this month.")
        backups.append((rank, Suggestion("backup", text, change, resolves)))
    backups.sort(key=lambda t: t[0])

    # --- swaps: an assigned employee who is off that day works it and takes a day off nearby ---
    swaps: list[Suggestion] = []
    for eid in sorted(primary):
        if status.get((eid, d)) not in (WEEKLY_OFF, HOLIDAY) or d in snap.leaves.get(eid, ()) or eid not in emp_by_id:
            continue
        for gap_days in range(1, 7):
            options = [d - timedelta(days=gap_days), d + timedelta(days=gap_days)]
            done = False
            for d2 in options:
                if status.get((eid, d2)) != WORK or d2 in snap.leaves.get(eid, ()):
                    continue
                changes = [Entry(eid, d, WORK, True, "manual"), Entry(eid, d2, WEEKLY_OFF, True, "manual")]
                resolves, clean = evaluate(changes)
                if clean:
                    name = emp_by_id[eid].name
                    swaps.append(Suggestion("swap", f"Move {name}'s day off from {d.day} {d.strftime('%b')} to "
                                            f"{d2.day} {d2.strftime('%b')} so they cover {proc.label or proc.name} on {d.day} {d.strftime('%b')}.",
                                            changes, resolves))
                    done = True
                    break
            if done:
                break

    # --- partial re-solve around the gap, everything else frozen ---
    days = month_days(snap.year, snap.month)
    window = (max(days[0], d - timedelta(days=3)), min(days[-1], d + timedelta(days=3)))
    solved = generate(snap, locked=entries, window=window, time_limit_s=5)
    old = {(e.employee_id, e.date): e for e in entries}
    diffs = [e for e in solved.entries if old.get((e.employee_id, e.date)) is not None
             and old[(e.employee_id, e.date)].status != e.status]
    resolve_sugg: list[Suggestion] = []
    if diffs:
        resolves, clean = evaluate(diffs)
        if resolves and clean:
            resolve_sugg.append(Suggestion(
                "resolve", f"Re-plan {window[0].day} {window[0].strftime('%b')} to {window[1].day} "
                           f"{window[1].strftime('%b')} automatically ({len(diffs)} day(s) change, other days stay as they are).",
                diffs, True))

    everything = [s for _, s in backups] + swaps + resolve_sugg
    everything.sort(key=lambda s: not s.resolves)  # stable: resolving fixes first, kinds keep their order
    return everything[:8]
