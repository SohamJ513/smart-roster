# NOTE: no `from __future__ import annotations` here: FastAPI must see the real model classes.
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m
from app import schemas as sc
from app.db import get_session

router = APIRouter()


def _cleanup_process(s: Session, pid: int) -> None:
    s.execute(delete(m.Assignment).where(m.Assignment.process_id == pid))
    s.execute(delete(m.CoverageOverride).where(m.CoverageOverride.process_id == pid))
    s.execute(update(m.RosterEntry).where(m.RosterEntry.cover_process_id == pid).values(cover_process_id=None))


def _before_delete_process(s: Session, obj: m.Process) -> None:
    _cleanup_process(s, obj.id)


def _before_delete_brand(s: Session, obj: m.Brand) -> None:
    for p in s.scalars(select(m.Process).where(m.Process.brand_id == obj.id)).all():
        _cleanup_process(s, p.id)
        s.delete(p)
    s.flush()


def _before_delete_employee(s: Session, obj: m.Employee) -> None:
    s.execute(update(m.Pod).where(m.Pod.lead_employee_id == obj.id).values(lead_employee_id=None))
    for model in (m.Assignment, m.Leave, m.RosterEntry):
        s.execute(delete(model).where(model.employee_id == obj.id))


def crud(path: str, Model, In, before_delete=None) -> None:
    Out = sc.with_id(In)
    prefix = f"/api/{path}"

    def commit(s: Session) -> None:
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            raise HTTPException(409, "Conflicts with existing data: a duplicate, an unknown reference, "
                                     "or something still in use.")

    @router.get(prefix, response_model=list[Out], tags=[path])
    def list_items(s: Session = Depends(get_session)):
        return s.scalars(select(Model).order_by(Model.id)).all()

    @router.get(prefix + "/{item_id}", response_model=Out, tags=[path])
    def get_item(item_id: int, s: Session = Depends(get_session)):
        obj = s.get(Model, item_id)
        if obj is None:
            raise HTTPException(404, "Not found")
        return obj

    @router.post(prefix, response_model=Out, status_code=201, tags=[path])
    def create_item(body: In, s: Session = Depends(get_session)):
        obj = Model(**body.model_dump())
        s.add(obj)
        commit(s)
        return obj

    @router.put(prefix + "/{item_id}", response_model=Out, tags=[path])
    def update_item(item_id: int, body: In, s: Session = Depends(get_session)):
        obj = s.get(Model, item_id)
        if obj is None:
            raise HTTPException(404, "Not found")
        for k, v in body.model_dump().items():
            setattr(obj, k, v)
        commit(s)
        return obj

    @router.delete(prefix + "/{item_id}", status_code=204, tags=[path])
    def delete_item(item_id: int, s: Session = Depends(get_session)):
        obj = s.get(Model, item_id)
        if obj is None:
            raise HTTPException(404, "Not found")
        if before_delete:
            before_delete(s, obj)
        s.delete(obj)
        commit(s)


crud("pods", m.Pod, sc.PodIn)
crud("employees", m.Employee, sc.EmployeeIn, _before_delete_employee)
crud("brands", m.Brand, sc.BrandIn, _before_delete_brand)
crud("processes", m.Process, sc.ProcessIn, _before_delete_process)
crud("assignments", m.Assignment, sc.AssignmentIn)
crud("holidays", m.Holiday, sc.HolidayIn)
crud("leaves", m.Leave, sc.LeaveIn)
crud("overrides", m.CoverageOverride, sc.OverrideIn)
