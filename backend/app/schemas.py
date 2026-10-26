from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import AttendanceStatus, Frequency, Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth / users ---------------------------------------------------------
class LoginIn(BaseModel):
    # An email, or a plain username such as the seeded "admin" account.
    email: str = Field(min_length=1, max_length=320)
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    groups: list["GroupBrief"] = []


class UserCreate(RegisterIn):
    role: Role = Role.user


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


# --- groups -----------------------------------------------------------------
class GroupBrief(ORM):
    id: int
    name: str


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    member_ids: list[int] = []


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    member_ids: list[int] | None = None


class GroupOut(ORM):
    id: int
    name: str
    description: str
    created_at: datetime
    member_ids: list[int]


# --- events -----------------------------------------------------------------
class RecurrenceIn(BaseModel):
    frequency: Frequency
    interval: int = Field(default=1, ge=1, le=52)
    weekdays: list[int] = Field(default=[], description="0=Mon … 6=Sun; weekly only")
    until: date | None = None
    count: int | None = Field(default=None, ge=1, le=200)
    timezone: str = "UTC"

    @field_validator("weekdays")
    @classmethod
    def valid_weekdays(cls, v: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("weekdays must be between 0 (Mon) and 6 (Sun)")
        return sorted(set(v))

    @model_validator(mode="after")
    def needs_end(self):
        if self.until is None and self.count is None:
            raise ValueError("recurrence needs 'until' or 'count'")
        return self


class SeriesOut(ORM):
    id: int
    frequency: Frequency
    interval: int
    weekdays: str
    until: date | None
    count: int | None
    timezone: str


class EventBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    location: str = Field(default="", max_length=200)
    starts_at: datetime
    ends_at: datetime
    check_in_opens_at: datetime | None = None
    check_in_closes_at: datetime | None = None
    late_after_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    group_ids: list[int] = Field(default=[], description="empty = open to all users")

    @field_validator("starts_at", "ends_at", "check_in_opens_at", "check_in_closes_at")
    @classmethod
    def require_tz(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("datetime must include a timezone offset")
        return v

    @model_validator(mode="after")
    def check_order(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.check_in_opens_at and self.check_in_closes_at:
            if self.check_in_closes_at <= self.check_in_opens_at:
                raise ValueError("check_in_closes_at must be after check_in_opens_at")
        return self


class EventCreate(EventBase):
    recurrence: RecurrenceIn | None = None


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    location: str | None = Field(default=None, max_length=200)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    check_in_opens_at: datetime | None = None
    check_in_closes_at: datetime | None = None
    late_after_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    group_ids: list[int] | None = None


class EventOut(ORM):
    id: int
    title: str
    description: str
    location: str
    starts_at: datetime
    ends_at: datetime
    check_in_opens_at: datetime
    check_in_closes_at: datetime
    late_after_minutes: int
    created_at: datetime
    series_id: int | None
    series: SeriesOut | None
    groups: list[GroupBrief]


class UserEventOut(EventOut):
    check_in_open: bool
    my_attendance_status: AttendanceStatus | None = None


# --- attendances --------------------------------------------------------------
class UserBrief(ORM):
    id: int
    email: str
    full_name: str


class EventBrief(ORM):
    id: int
    title: str
    starts_at: datetime


class AttendanceOut(ORM):
    id: int
    event_id: int
    user_id: int
    activity_summary: str
    location_note: str
    declaration: bool
    is_late: bool
    status: AttendanceStatus
    review_comment: str
    reviewed_at: datetime | None
    submitted_at: datetime
    user: UserBrief
    event: EventBrief


class AttendancePage(BaseModel):
    items: list[AttendanceOut]
    total: int
    page: int
    page_size: int


class AttendanceReview(BaseModel):
    status: AttendanceStatus
    review_comment: str = ""


class StatsOut(BaseModel):
    total_users: int
    total_events: int
    total_attendances: int
    pending: int
    approved: int
    rejected: int
    late: int
    upcoming_events: int
    recent_events: list[dict]


UserOut.model_rebuild()
TokenOut.model_rebuild()
