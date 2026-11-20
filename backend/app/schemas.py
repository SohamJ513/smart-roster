import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Weekday = Field(ge=0, le=6)


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PodIn(BaseModel):
    name: str = Field(min_length=1)
    lead_employee_id: int | None = None


class EmployeeIn(BaseModel):
    name: str = Field(min_length=1)
    pod_id: int
    weekly_off_mode: Literal["fixed", "flexible"] = "flexible"
    fixed_weekday: int | None = Field(default=None, ge=0, le=6)
    preferred_off_weekday: int | None = Field(default=None, ge=0, le=6)
    active: bool = True

    @model_validator(mode="after")
    def _fixed_needs_weekday(self):
        if self.weekly_off_mode == "fixed" and self.fixed_weekday is None:
            raise ValueError("fixed weekly off needs fixed_weekday")
        return self


class BrandIn(BaseModel):
    name: str = Field(min_length=1)
    default_weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    default_holidays_off: bool = True

    @model_validator(mode="after")
    def _weekdays(self):
        _check_weekdays(self.default_weekdays)
        return self


class ProcessIn(BaseModel):
    brand_id: int
    name: str = Field(min_length=1)
    weekdays: list[int]
    holidays_off: bool
    min_staff: int = Field(default=1, ge=0)
    shift_label: str = "General"
    shift_start: dt.time | None = None
    shift_end: dt.time | None = None

    @model_validator(mode="after")
    def _check(self):
        _check_weekdays(self.weekdays)
        if (self.shift_start is None) != (self.shift_end is None):
            raise ValueError("shift_start and shift_end must be set together")
        return self


class OverrideIn(BaseModel):
    process_id: int
    weekday: int | None = Field(default=None, ge=0, le=6)
    date: dt.date | None = None
    min_staff: int = Field(ge=0)

    @model_validator(mode="after")
    def _one_of(self):
        if (self.weekday is None) == (self.date is None):
            raise ValueError("set exactly one of weekday or date")
        return self


class AssignmentIn(BaseModel):
    employee_id: int
    process_id: int
    role: Literal["primary", "backup"] = "primary"


class HolidayIn(BaseModel):
    date: dt.date
    name: str = Field(min_length=1)


class LeaveIn(BaseModel):
    employee_id: int
    date: dt.date
    type: Literal["planned", "comp_off"] = "planned"
    status: Literal["approved"] = "approved"


def _check_weekdays(days: list[int]) -> None:
    if not days or any(not 0 <= d <= 6 for d in days) or len(set(days)) != len(days):
        raise ValueError("weekdays must be a non-empty list of unique numbers 0 (Mon) to 6 (Sun)")


def with_id(cls: type[BaseModel]) -> type[Out]:
    return type(cls.__name__.replace("In", "Out"), (cls, Out), {})


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    severity: str
    code: str
    message: str
    date: dt.date | None = None
    process_id: int | None = None
    employee_id: int | None = None


STATUS = Literal["WORK", "WEEKLY_OFF", "HOLIDAY", "LEAVE", "COMP_OFF"]


class EntryChange(BaseModel):
    employee_id: int
    date: dt.date
    status: STATUS
    cover_process_id: int | None = None


class EntryOut(EntryChange):
    model_config = ConfigDict(from_attributes=True)
    locked: bool = False
    source: str = "solver"


class GenerateIn(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class LeaveItem(BaseModel):
    employee_id: int
    date: dt.date
    type: Literal["planned", "comp_off"] = "planned"


class LeavesIn(BaseModel):
    leaves: list[LeaveItem] = Field(min_length=1)


class PublishIn(BaseModel):
    acknowledged_issue_codes: list[str] = Field(default_factory=list)


class ApplySuggestionIn(BaseModel):
    entry_changes: list[EntryChange] = Field(min_length=1)
