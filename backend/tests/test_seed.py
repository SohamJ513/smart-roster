from collections import defaultdict

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app import models as m
from app.db import Base
from app.domain import ERROR
from app.loader import load_snapshot
from app.seed import DEMO_MONTH, DEMO_YEAR, reset_demo, seed_if_empty
from app.solver import generate


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        seed_if_empty(s)
        yield s


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def brand_staff(session):
    """brand_id -> {employee_id: set(process_id)} using primary assignments only."""
    rows = session.execute(
        select(m.Process.brand_id, m.Assignment.employee_id, m.Process.id)
        .join(m.Assignment, m.Assignment.process_id == m.Process.id)
        .where(m.Assignment.role == "primary")).all()
    out = defaultdict(lambda: defaultdict(set))
    for brand_id, emp_id, pid in rows:
        out[brand_id][emp_id].add(pid)
    return out


def test_seed_has_at_least_30_employees_and_4_pods(session):
    assert count(session, m.Employee) >= 30
    assert count(session, m.Pod) == 4
    leads = session.scalars(select(m.Pod.lead_employee_id)).all()
    assert None not in leads and len(set(leads)) == 4


def test_about_80_percent_of_brands_are_single_resource(session):
    staff = brand_staff(session)
    total = count(session, m.Brand)
    single = sum(1 for b in staff.values() if len(b) == 1)
    assert len(staff) == total
    assert 0.75 <= single / total <= 0.85


def test_has_multi_employee_brand_with_shared_process_and_with_separate_processes(session):
    staff = brand_staff(session)
    multi = [b for b in staff.values() if len(b) >= 2]
    assert all(2 <= len(b) <= 3 for b in multi)
    shared = [b for b in multi if any(sum(pid in procs for procs in b.values()) >= 2
                                      for pid in set().union(*b.values()))]
    separate = [b for b in multi if any(a.isdisjoint(c) for a in b.values() for c in b.values() if a is not c)]
    assert shared and separate


def test_has_overlapping_shift_window_processes(session):
    windowed = session.execute(select(m.Process.brand_id).where(m.Process.shift_start.is_not(None))).scalars().all()
    assert len(windowed) >= 2 and len(set(windowed)) < len(windowed)  # two windowed processes in one brand


def test_has_processes_needing_two_people_and_all_rule_presets(session):
    procs = session.scalars(select(m.Process)).all()
    overrides = defaultdict(list)
    for o in session.scalars(select(m.CoverageOverride)):
        overrides[o.process_id].append(o.min_staff)
    needing_two = [p for p in procs if p.min_staff >= 2 or max(overrides[p.id], default=0) >= 2]
    assert len(needing_two) >= 2
    rules = {(tuple(sorted(p.weekdays)), p.holidays_off) for p in procs}
    assert ((0, 1, 2, 3, 4, 5, 6), False) in rules      # 365 days
    assert ((0, 1, 2, 3, 4, 5, 6), True) in rules       # daily except holidays
    assert ((0, 1, 2, 3, 4, 5), True) in rules          # Sundays and holidays off


def test_seed_is_idempotent(session):
    before = {mod: count(session, mod) for mod in (m.Employee, m.Brand, m.Process, m.Assignment, m.Leave, m.Holiday)}
    assert seed_if_empty(session) is False
    assert before == {mod: count(session, mod) for mod in before}


def test_reset_demo_restores_seed_counts(session):
    before = count(session, m.Employee), count(session, m.Assignment)
    session.add(m.Holiday(date=__import__("datetime").date(2026, 12, 1), name="Extra"))
    session.commit()
    reset_demo(session)
    assert (count(session, m.Employee), count(session, m.Assignment)) == before
    assert session.scalar(select(func.count()).select_from(m.Holiday).where(m.Holiday.name == "Extra")) == 0


def test_loader_comp_offs_are_subset_of_leaves(session):
    snap = load_snapshot(session, DEMO_YEAR, DEMO_MONTH)
    assert snap.comp_offs and all(snap.comp_offs[e] <= snap.leaves[e] for e in snap.comp_offs)
    assert all(d.year == DEMO_YEAR and d.month == DEMO_MONTH for ds in snap.leaves.values() for d in ds)


def test_demo_month_generates_with_no_errors(session):
    snap = load_snapshot(session, DEMO_YEAR, DEMO_MONTH)
    res = generate(snap, time_limit_s=20)
    assert [i for i in res.issues if i.severity == ERROR] == []


def test_loader_gives_every_process_a_brand_prefixed_label(session):
    snap = load_snapshot(session, DEMO_YEAR, DEMO_MONTH)
    assert snap.processes and all(" · " in p.label for p in snap.processes)
