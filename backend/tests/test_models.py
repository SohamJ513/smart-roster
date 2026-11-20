import pytest
from datetime import date
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base
from app import models as m


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _base(session):
    pod = m.Pod(name="Pod A")
    session.add(pod)
    session.flush()
    brand = m.Brand(name="Glow")
    session.add(brand)
    session.flush()
    p1 = m.Process(brand_id=brand.id, name="CS")
    p2 = m.Process(brand_id=brand.id, name="ACC")
    e1 = m.Employee(name="Asha", pod_id=pod.id)
    e2 = m.Employee(name="Ravi", pod_id=pod.id)
    session.add_all([p1, p2, e1, e2])
    session.flush()
    return p1, p2, e1, e2


def test_create_brand_with_two_processes_and_assignments(session):
    p1, p2, e1, e2 = _base(session)
    session.add_all([
        m.Assignment(employee_id=e1.id, process_id=p1.id, role="primary"),
        m.Assignment(employee_id=e1.id, process_id=p2.id, role="primary"),
        m.Assignment(employee_id=e2.id, process_id=p1.id, role="primary"),
    ])
    session.commit()
    n_e1 = session.scalar(select(func.count()).select_from(m.Assignment).where(m.Assignment.employee_id == e1.id))
    n_p1 = session.scalar(select(func.count()).select_from(m.Assignment).where(m.Assignment.process_id == p1.id))
    assert n_e1 == 2
    assert n_p1 == 2  # a second employee can share the same process


def test_leave_unique_per_employee_date(session):
    _, _, e1, _ = _base(session)
    session.add(m.Leave(employee_id=e1.id, date=date(2026, 12, 5), type="planned"))
    session.commit()
    session.add(m.Leave(employee_id=e1.id, date=date(2026, 12, 5), type="comp_off"))
    with pytest.raises(IntegrityError):
        session.commit()
