# NOTE: no `from __future__ import annotations` here: FastAPI must see the real model classes.
import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app import schemas as sc
from app.calendar_rules import month_days
from app.changes import impact, suggest
from app.coverage import coverage_grid
from app.domain import ERROR, Entry, Issue, Snapshot
from app.loader import load_snapshot
from app.solver import generate
from app.validator import validate
from app.db import get_session

router = APIRouter(prefix="/api/rosters", tags=["rosters"])

def _safe_cell(text: str) -> str:
    """Stop spreadsheet apps from running a name like =HYPERLINK(...) as a formula."""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


ABBREV = {"WORK": "W", "WEEKLY_OFF": "WO", "HOLIDAY": "H", "LEAVE": "L", "COMP_OFF": "CO"}


def _roster(s: Session, rid: int) -> m.Roster:
    roster = s.get(m.Roster, rid)
    if roster is None:
        raise HTTPException(404, "Roster not found")
    return roster


def _entries(s: Session, rid: int) -> list[Entry]:
    rows = s.scalars(select(m.RosterEntry).where(m.RosterEntry.roster_id == rid)
                     .order_by(m.RosterEntry.employee_id, m.RosterEntry.date))
    return [Entry(r.employee_id, r.date, r.status, r.locked, r.source, r.cover_process_id) for r in rows]


def _load(s: Session, roster: m.Roster) -> tuple[Snapshot, list[Entry]]:
    return load_snapshot(s, roster.year, roster.month), _entries(s, roster.id)


def _save(s: Session, rid: int, entries: list[Entry]) -> None:
    existing = {(r.employee_id, r.date): r for r in
                s.scalars(select(m.RosterEntry).where(m.RosterEntry.roster_id == rid))}
    for e in entries:
        row = existing.get((e.employee_id, e.date))
        if row is None:
            s.add(m.RosterEntry(roster_id=rid, employee_id=e.employee_id, date=e.date, status=e.status,
                                locked=e.locked, source=e.source, cover_process_id=e.cover_process_id))
        else:
            row.status, row.locked, row.source, row.cover_process_id = e.status, e.locked, e.source, e.cover_process_id
    roster = s.get(m.Roster, rid)
    if roster is not None and roster.status == "published":
        roster.status, roster.acknowledged_codes = "draft", []   # an edit invalidates what was published
    s.commit()


def _check(snap: Snapshot, employee_id: int, d: date, cover_process_id: int | None = None) -> None:
    if employee_id not in {e.id for e in snap.employees}:
        raise HTTPException(422, f"Unknown employee {employee_id}")
    if d not in set(month_days(snap.year, snap.month)):
        raise HTTPException(422, f"{d} is outside the roster month")
    if cover_process_id is not None and cover_process_id not in {p.id for p in snap.processes}:
        raise HTTPException(422, f"Unknown process {cover_process_id}")


def _out(issues: list[Issue]) -> list[dict]:
    return [sc.IssueOut.model_validate(i).model_dump(mode="json") for i in issues]


def _key(i: Issue) -> tuple:
    return (i.code, i.date, i.process_id, i.employee_id)


def _delta(before: list[Issue], after: list[Issue]) -> dict:
    bk, ak = {_key(i) for i in before}, {_key(i) for i in after}
    return {"issues": _out(after),
            "new_issues": _out([i for i in after if _key(i) not in bk]),
            "resolved_issues": _out([i for i in before if _key(i) not in ak])}


@router.get("")
def list_rosters(s: Session = Depends(get_session)):
    return [{"id": r.id, "year": r.year, "month": r.month, "status": r.status, "version": r.version}
            for r in s.scalars(select(m.Roster).order_by(m.Roster.id.desc()))]


@router.post("/generate")
def generate_roster(body: sc.GenerateIn, s: Session = Depends(get_session)):
    snap = load_snapshot(s, body.year, body.month)
    result = generate(snap, time_limit_s=10)
    roster = m.Roster(year=body.year, month=body.month, status="draft", acknowledged_codes=[])
    s.add(roster)
    s.flush()
    _save(s, roster.id, result.entries)
    return {"roster_id": roster.id, "issues": _out(result.issues)}


@router.get("/{rid}")
def get_roster(rid: int, s: Session = Depends(get_session)):
    roster = _roster(s, rid)
    return {"id": roster.id, "year": roster.year, "month": roster.month, "status": roster.status,
            "version": roster.version, "acknowledged_codes": roster.acknowledged_codes,
            "entries": [sc.EntryOut.model_validate(e).model_dump(mode="json") for e in _entries(s, rid)]}


@router.get("/{rid}/validate")
def validate_roster(rid: int, s: Session = Depends(get_session)):
    snap, entries = _load(s, _roster(s, rid))
    return _out(validate(snap, entries))


@router.get("/{rid}/coverage")
def coverage(rid: int, s: Session = Depends(get_session)):
    snap, entries = _load(s, _roster(s, rid))
    return [{"process_id": c.process_id, "date": c.date.isoformat(), "required": c.required,
             "working": c.working, "employee_ids": c.employee_ids} for c in coverage_grid(snap, entries)]


@router.patch("/{rid}/entries")
def patch_entry(rid: int, body: sc.EntryChange, s: Session = Depends(get_session)):
    snap, entries = _load(s, _roster(s, rid))
    _check(snap, body.employee_id, body.date, body.cover_process_id)
    before = validate(snap, entries)
    new = Entry(body.employee_id, body.date, body.status, True, "manual",
                body.cover_process_id if body.status == "WORK" else None)
    _save(s, rid, [new])
    return _delta(before, validate(snap, _entries(s, rid)))


@router.post("/{rid}/impact")
def what_if(rid: int, body: sc.LeavesIn, s: Session = Depends(get_session)):
    snap, entries = _load(s, _roster(s, rid))
    for lv in body.leaves:
        _check(snap, lv.employee_id, lv.date)
    res = impact(snap, entries, _leave_map(body))
    return {"before": _out(res.before), "after": _out(res.after),
            "new_issues": _out(res.new_issues), "resolved_issues": _out(res.resolved_issues)}


def _leave_map(body: sc.LeavesIn) -> dict[int, frozenset[date]]:
    out: dict[int, set[date]] = {}
    for lv in body.leaves:
        out.setdefault(lv.employee_id, set()).add(lv.date)
    return {k: frozenset(v) for k, v in out.items()}


@router.post("/{rid}/apply-leave")
def apply_leave(rid: int, body: sc.LeavesIn, s: Session = Depends(get_session)):
    snap, entries = _load(s, _roster(s, rid))
    for lv in body.leaves:
        _check(snap, lv.employee_id, lv.date)
    res = impact(snap, entries, _leave_map(body))
    kinds = {(lv.employee_id, lv.date): lv.type for lv in body.leaves}
    for (eid, d), kind in kinds.items():
        if s.scalar(select(m.Leave.id).where(m.Leave.employee_id == eid, m.Leave.date == d)) is None:
            s.add(m.Leave(employee_id=eid, date=d, type=kind))
    s.flush()
    final = [Entry(e.employee_id, e.date, "COMP_OFF", e.locked, e.source)
             if kinds.get((e.employee_id, e.date)) == "comp_off" else e for e in res.entries_after]
    _save(s, rid, final)
    return _delta(res.before, validate(res.snapshot_after, final))


@router.get("/{rid}/suggestions")
def get_suggestions(rid: int, date: date, process_id: int, code: str = Query(...), s: Session = Depends(get_session)):
    snap, entries = _load(s, _roster(s, rid))
    issue = next((i for i in validate(snap, entries)
                  if i.code == code and i.date == date and i.process_id == process_id), None)
    if issue is None:
        raise HTTPException(404, "No such issue in this roster (it may already be resolved)")
    return [{"kind": x.kind, "description": x.description, "resolves": x.resolves,
             "entry_changes": [sc.EntryChange.model_validate(
                 {"employee_id": c.employee_id, "date": c.date, "status": c.status,
                  "cover_process_id": c.cover_process_id}).model_dump(mode="json") for c in x.entry_changes]}
            for x in suggest(snap, entries, issue)]


@router.post("/{rid}/apply-suggestion")
def apply_suggestion(rid: int, body: sc.ApplySuggestionIn, s: Session = Depends(get_session)):
    snap, entries = _load(s, _roster(s, rid))
    for c in body.entry_changes:
        _check(snap, c.employee_id, c.date, c.cover_process_id)
    before = validate(snap, entries)
    _save(s, rid, [Entry(c.employee_id, c.date, c.status, True, "manual",
                         c.cover_process_id if c.status == "WORK" else None) for c in body.entry_changes])
    return _delta(before, validate(snap, _entries(s, rid)))


@router.post("/{rid}/publish")
def publish(rid: int, body: sc.PublishIn, s: Session = Depends(get_session)):
    roster = _roster(s, rid)
    snap, entries = _load(s, roster)
    errs = [i for i in validate(snap, entries) if i.severity == ERROR]
    err_codes = {i.code for i in errs}
    unacknowledged = err_codes - set(body.acknowledged_issue_codes)
    if unacknowledged:
        raise HTTPException(409, {"message": "Unresolved errors must be acknowledged before publishing: "
                                              + ", ".join(sorted(unacknowledged)),
                                  "issues": _out(errs)})
    roster.status = "published"
    roster.acknowledged_codes = sorted(err_codes)
    s.commit()
    return {"status": roster.status, "acknowledged_codes": roster.acknowledged_codes}


@router.get("/{rid}/export.csv")
def export_csv(rid: int, s: Session = Depends(get_session)):
    roster = _roster(s, rid)
    days = month_days(roster.year, roster.month)
    pods = {p.id: p.name for p in s.scalars(select(m.Pod))}
    status = {(e.employee_id, e.date): e.status for e in _entries(s, rid)}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Employee", "Pod"] + [f"{d.day:02d} {d.strftime('%a')}" for d in days])
    for e in s.scalars(select(m.Employee).where(m.Employee.active).order_by(m.Employee.id)):
        w.writerow([_safe_cell(e.name), _safe_cell(pods.get(e.pod_id, ""))] + [ABBREV.get(status.get((e.id, d), ""), "") for d in days])
    return Response(out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="roster-{roster.year}-{roster.month:02d}.csv"'})
