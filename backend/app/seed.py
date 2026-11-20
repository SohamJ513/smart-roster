"""Realistic, deterministic demo data: 32 employees, 4 pods, 25 brands (20 single-resource)."""
from __future__ import annotations

from datetime import date, time

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app import models as m

DEMO_YEAR, DEMO_MONTH = 2026, 12

NAMES = [
    "Asha Menon", "Ravi Kulkarni", "Neha Iyer", "Karan Malhotra", "Priya Nair", "Sandeep Rao", "Divya Joshi", "Arjun Bhat",
    "Meera Pillai", "Rohit Sharma", "Ananya Das", "Vikram Singh", "Pooja Reddy", "Imran Khan", "Sneha Patil", "Aditya Verma",
    "Kavya Krishnan", "Manish Gupta", "Ritu Agarwal", "Suresh Babu", "Tanvi Shah", "Harsh Vardhan", "Lakshmi Narayan",
    "Faisal Ahmed", "Nidhi Kapoor", "Gaurav Mehta", "Shreya Ghosh", "Yash Chopra", "Bhavna Desai", "Omkar Jadhav",
    "Zoya Siddiqui", "Pranav Nambiar",
]
PODS = ["Alpha", "Beta", "Gamma", "Delta"]  # employees 1-8, 9-16, 17-24, 25-32; first of each is the lead

ALL = [0, 1, 2, 3, 4, 5, 6]
RULES = {  # name -> (operating weekdays, holidays_off)
    "365": (ALL, False),
    "DAILY_NO_HOL": (ALL, True),            # every day except public holidays
    "MON_SAT_NO_HOL": ([0, 1, 2, 3, 4, 5], True),   # Sundays and holidays off
    "MON_SAT": ([0, 1, 2, 3, 4, 5], False),
    "MON_FRI_NO_HOL": ([0, 1, 2, 3, 4], True),
}

# process spec: (name, rule, min_staff, {weekday: min_staff override}, (shift_label, start, end), [(employee_no, role)])
GEN = ("General", None, None)
MORNING = ("Morning", time(6), time(14))
EVENING = ("Evening", time(14), time(22))


def P(name, rule, staff, min_staff=1, overrides=None, shift=GEN):
    return (name, rule, min_staff, overrides or {}, shift, [(e, "primary") for e in staff])


MULTI = {  # brands with 2-3 employees (spec: separate processes AND shared processes)
    "Lumen Skincare": [P("CS", "365", [1, 2]), P("ACC", "MON_SAT_NO_HOL", [3]), P("NDR", "MON_SAT_NO_HOL", [2, 3])],
    "Nimbus Home": [P("CS", "MON_SAT_NO_HOL", [4, 5, 6], min_staff=2), P("ACC", "MON_SAT_NO_HOL", [6]),
                    P("Retention", "MON_SAT_NO_HOL", [4, 5])],
    "Verve Fitness": [P("CS", "DAILY_NO_HOL", [7, 8]), P("NDR", "MON_SAT_NO_HOL", [7, 8])],
    "Orchid Naturals": [P("CS Morning", "MON_SAT_NO_HOL", [9], shift=MORNING),
                        P("CS Evening", "MON_SAT_NO_HOL", [10], shift=EVENING),
                        P("ACC", "MON_SAT_NO_HOL", [9, 10])],
    "Saffron Foods": [P("CS", "365", [11, 12, 13], overrides={5: 2, 6: 2}),
                      P("NDR", "DAILY_NO_HOL", [12, 13]), P("ACC", "MON_SAT_NO_HOL", [11])],
}

# 20 single-resource brands: (name, [(process, rule), ...]); brand i -> employee 13+i, brand 20 -> employee 14
SINGLE = [
    ("Bloom & Co", [("CS", "MON_SAT_NO_HOL")]),
    ("Trailmate Outdoors", [("CS", "MON_SAT_NO_HOL"), ("ACC", "MON_SAT_NO_HOL")]),
    ("Urban Loom", [("CS", "MON_SAT_NO_HOL"), ("NDR", "MON_SAT_NO_HOL")]),
    ("Kiwi Kids", [("CS", "MON_FRI_NO_HOL")]),
    ("Aurum Jewels", [("CS", "MON_SAT_NO_HOL"), ("ACC", "MON_SAT_NO_HOL"), ("NDR", "MON_SAT_NO_HOL")]),
    ("PureRoots", [("CS", "MON_SAT")]),
    ("Pixel Gadgets", [("CS", "MON_FRI_NO_HOL"), ("NDR", "MON_FRI_NO_HOL")]),
    ("Zenith Wear", [("CS", "MON_SAT_NO_HOL"), ("Retention", "MON_SAT_NO_HOL")]),
    ("Chai Culture", [("CS", "MON_SAT_NO_HOL")]),
    ("Nova Footwear", [("CS", "MON_SAT_NO_HOL"), ("ACC", "MON_SAT_NO_HOL")]),
    ("Hearth & Home", [("CS", "MON_SAT_NO_HOL"), ("NDR", "MON_SAT_NO_HOL")]),
    ("Bolt Bikes", [("CS", "MON_SAT")]),
    ("Mintleaf Tea", [("CS", "MON_SAT_NO_HOL"), ("ACC", "MON_SAT_NO_HOL")]),
    ("Peak Protein", [("CS", "MON_SAT_NO_HOL"), ("Retention", "MON_SAT_NO_HOL")]),
    ("Lotus Ayurveda", [("CS", "MON_SAT_NO_HOL"), ("NDR", "MON_SAT_NO_HOL")]),
    ("Quill Stationery", [("CS", "MON_SAT_NO_HOL")]),
    ("Ember Candles", [("CS", "MON_SAT_NO_HOL"), ("ACC", "MON_SAT_NO_HOL")]),
    ("Drift Denim", [("CS", "MON_SAT_NO_HOL"), ("NDR", "MON_SAT_NO_HOL")]),
    ("Sage Pets", [("CS", "MON_SAT_NO_HOL"), ("ACC", "MON_SAT_NO_HOL"), ("Retention", "MON_SAT_NO_HOL")]),
    ("Cobalt Audio", [("CS", "MON_FRI_NO_HOL")]),
]

EMP_ATTRS = {  # employee no -> overrides
    2: dict(preferred_off_weekday=2),                         # prefers Wednesday off
    4: dict(weekly_off_mode="fixed", fixed_weekday=2),        # fixed Wednesday weekly off
    15: dict(preferred_off_weekday=2),                        # single-resource: preference will lose to coverage
    20: dict(preferred_off_weekday=4),
}
BACKUPS = [(31, "Pixel Gadgets", "CS"), (26, "Lumen Skincare", "CS")]  # (employee no, brand, process)

HOLIDAYS = [  # fictional/approximate; editable in the app
    (date(2026, 11, 8), "Diwali"), (date(2026, 12, 25), "Christmas"),
    (date(2027, 1, 1), "New Year's Day"), (date(2027, 1, 26), "Republic Day"),
]
LEAVES = [  # none touches a single-resource employee, so the seeded roster is clean
    (2, date(2026, 12, 14), "planned"), (2, date(2026, 12, 15), "planned"), (5, date(2026, 12, 22), "planned"),
    (12, date(2026, 12, 10), "comp_off"), (1, date(2026, 12, 28), "planned"),
    (7, date(2026, 12, 3), "planned"), (13, date(2026, 12, 19), "planned"),
]


def _populate(session: Session) -> None:
    pods = [m.Pod(name=n) for n in PODS]
    session.add_all(pods)
    session.flush()
    emps = []
    for i, name in enumerate(NAMES, start=1):
        emps.append(m.Employee(name=name, pod_id=pods[(i - 1) // 8].id, **EMP_ATTRS.get(i, {})))
    session.add_all(emps)
    session.flush()
    for k, pod in enumerate(pods):
        pod.lead_employee_id = emps[k * 8].id

    proc_ids: dict[tuple[str, str], int] = {}

    def add_process(brand: m.Brand, name: str, rule: str, min_staff=1, overrides=None, shift=GEN) -> m.Process:
        weekdays, hol_off = RULES[rule]
        p = m.Process(brand_id=brand.id, name=name, weekdays=list(weekdays), holidays_off=hol_off,
                      min_staff=min_staff, shift_label=shift[0], shift_start=shift[1], shift_end=shift[2])
        session.add(p)
        session.flush()
        proc_ids[(brand.name, name)] = p.id
        for wd, n in (overrides or {}).items():
            session.add(m.CoverageOverride(process_id=p.id, weekday=wd, min_staff=n))
        return p

    for bname, specs in MULTI.items():
        brand = m.Brand(name=bname)
        session.add(brand)
        session.flush()
        for name, rule, min_staff, overrides, shift, staff in specs:
            p = add_process(brand, name, rule, min_staff, overrides, shift)
            for eno, role in staff:
                session.add(m.Assignment(employee_id=emps[eno - 1].id, process_id=p.id, role=role))

    for idx, (bname, procs) in enumerate(SINGLE, start=1):
        brand = m.Brand(name=bname)
        session.add(brand)
        session.flush()
        owner = emps[(13 + idx if idx <= 19 else 14) - 1]
        for pname, rule in procs:
            p = add_process(brand, pname, rule)
            session.add(m.Assignment(employee_id=owner.id, process_id=p.id, role="primary"))

    for eno, bname, pname in BACKUPS:
        session.add(m.Assignment(employee_id=emps[eno - 1].id, process_id=proc_ids[(bname, pname)], role="backup"))
    for d, name in HOLIDAYS:
        session.add(m.Holiday(date=d, name=name))
    for eno, d, kind in LEAVES:
        session.add(m.Leave(employee_id=emps[eno - 1].id, date=d, type=kind))


def seed_if_empty(session: Session) -> bool:
    if session.scalar(select(func.count()).select_from(m.Employee)):
        return False
    _populate(session)
    session.commit()
    return True


def reset_demo(session: Session) -> None:
    for model in (m.RosterEntry, m.Roster, m.Leave, m.Holiday, m.Assignment, m.CoverageOverride, m.Process, m.Brand):
        session.execute(delete(model))
    session.execute(update(m.Pod).values(lead_employee_id=None))
    session.execute(delete(m.Employee))
    session.execute(delete(m.Pod))
    session.commit()
    _populate(session)
    session.commit()
