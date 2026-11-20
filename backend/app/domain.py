"""Pure domain types shared by the scheduling core. No DB, no HTTP."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time

WORK = "WORK"
WEEKLY_OFF = "WEEKLY_OFF"
HOLIDAY = "HOLIDAY"
LEAVE = "LEAVE"
COMP_OFF = "COMP_OFF"
STATUSES = (WORK, WEEKLY_OFF, HOLIDAY, LEAVE, COMP_OFF)

ERROR = "ERROR"
WARNING = "WARNING"


@dataclass(frozen=True)
class ProcessCfg:
    id: int
    brand_id: int
    name: str
    weekdays: frozenset[int]
    holidays_off: bool
    min_staff: int
    overrides_by_weekday: dict[int, int] = field(default_factory=dict)
    overrides_by_date: dict[date, int] = field(default_factory=dict)
    shift_start: time | None = None
    shift_end: time | None = None
    label: str = ""  # display name such as "Glow · CS"; falls back to `name`


@dataclass(frozen=True)
class EmployeeCfg:
    id: int
    name: str
    pod_id: int
    weekly_off_mode: str = "flexible"  # "fixed" or "flexible"
    fixed_weekday: int | None = None
    preferred_off_weekday: int | None = None


@dataclass(frozen=True)
class AssignmentCfg:
    employee_id: int
    process_id: int
    role: str = "primary"  # "primary" or "backup"


@dataclass(frozen=True)
class Params:
    max_consecutive: int = 6
    min_off_days: int = 4


@dataclass(frozen=True)
class Snapshot:
    year: int
    month: int
    employees: list[EmployeeCfg]
    processes: list[ProcessCfg]
    assignments: list[AssignmentCfg]
    holidays: frozenset[date]
    leaves: dict[int, frozenset[date]]
    params: Params = field(default_factory=Params)
    # subset of `leaves` days that are comp-offs (shown as COMP_OFF instead of LEAVE)
    comp_offs: dict[int, frozenset[date]] = field(default_factory=dict)


@dataclass(frozen=True)
class Entry:
    employee_id: int
    date: date
    status: str
    locked: bool = False
    source: str = "solver"  # "solver" or "manual"
    # set on a WORK entry when the employee is covering a process they are not assigned to (backup cover)
    cover_process_id: int | None = None


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    date: date | None = None
    process_id: int | None = None
    employee_id: int | None = None
