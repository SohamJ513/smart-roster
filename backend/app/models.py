from __future__ import annotations

from datetime import date, time

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Pod(Base):
    __tablename__ = "pod"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    lead_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employee.id", use_alter=True), nullable=True)


class Employee(Base):
    __tablename__ = "employee"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    pod_id: Mapped[int] = mapped_column(ForeignKey("pod.id"))
    weekly_off_mode: Mapped[str] = mapped_column(String, default="flexible")
    fixed_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_off_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Brand(Base):
    __tablename__ = "brand"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    default_weekdays: Mapped[list] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4, 5, 6])
    default_holidays_off: Mapped[bool] = mapped_column(Boolean, default=True)


class Process(Base):
    __tablename__ = "process"
    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brand.id"))
    name: Mapped[str] = mapped_column(String)
    weekdays: Mapped[list] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4, 5, 6])
    holidays_off: Mapped[bool] = mapped_column(Boolean, default=True)
    min_staff: Mapped[int] = mapped_column(Integer, default=1)
    shift_label: Mapped[str] = mapped_column(String, default="General")
    shift_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    shift_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    __table_args__ = (UniqueConstraint("brand_id", "name"),)


class CoverageOverride(Base):
    __tablename__ = "coverage_override"
    id: Mapped[int] = mapped_column(primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id"))
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    min_staff: Mapped[int] = mapped_column(Integer)


class Assignment(Base):
    __tablename__ = "assignment"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employee.id"))
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id"))
    role: Mapped[str] = mapped_column(String, default="primary")
    __table_args__ = (UniqueConstraint("employee_id", "process_id"),)


class Holiday(Base):
    __tablename__ = "holiday"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True)
    name: Mapped[str] = mapped_column(String)


class Leave(Base):
    __tablename__ = "leave"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employee.id"))
    date: Mapped[date] = mapped_column(Date)
    type: Mapped[str] = mapped_column(String, default="planned")  # planned | comp_off
    status: Mapped[str] = mapped_column(String, default="approved")
    __table_args__ = (UniqueConstraint("employee_id", "date"),)


class Roster(Base):
    __tablename__ = "roster"
    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft | published
    version: Mapped[int] = mapped_column(Integer, default=1)
    acknowledged_codes: Mapped[list] = mapped_column(JSON, default=list)


class RosterEntry(Base):
    __tablename__ = "roster_entry"
    id: Mapped[int] = mapped_column(primary_key=True)
    roster_id: Mapped[int] = mapped_column(ForeignKey("roster.id"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employee.id"))
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String, default="solver")
    cover_process_id: Mapped[int | None] = mapped_column(ForeignKey("process.id"), nullable=True)
    __table_args__ = (UniqueConstraint("roster_id", "employee_id", "date"),)
