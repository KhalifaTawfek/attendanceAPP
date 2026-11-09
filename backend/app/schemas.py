from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import AttendanceStatus, Frequency, Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth / users ---------------------------------------------------------
class LoginIn(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


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

    @field_validator("password")
    @classmethod
    def password_limit(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


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
    source: str
    user: UserBrief
    event: EventBrief


class AttendancePage(BaseModel):
    items: list[AttendanceOut]
    total: int
    page: int
    page_size: int


class EventTurnout(BaseModel):
    event_id: int
    title: str
    starts_at: datetime
    count: int
    approved: int
    from_lists: int
    expected: int


class TrendPoint(BaseModel):
    period: date
    self: int
    ocr: int
    late: int


class StudentRate(BaseModel):
    user_id: int
    full_name: str
    attended: int
    expected: int
    rate: float


class GroupRate(BaseModel):
    group_id: int
    group: str
    attended: int
    expected: int
    rate: float


class AttendanceSummary(BaseModel):
    total: int
    late: int
    by_status: dict[str, int]
    by_source: dict[str, int]
    per_event: list[EventTurnout]  # oldest -> newest, at most 40 events
    per_group: list[dict]
    top_users: list[dict]
    # volume over the filtered attendances
    granularity: str
    trend: list[TrendPoint]
    by_weekday: list[int]  # Mon..Sun, in the requested timezone
    # rates over past events in scope (non-rejected attendance = present)
    events_in_scope: int
    students_in_scope: int
    avg_turnout: float | None
    at_risk: int  # students below 50% with at least 2 expected events
    students_low: list[StudentRate]
    students_high: list[StudentRate]
    group_rates: list[GroupRate]


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


# --- OCR imports ------------------------------------------------------------
class OcrSuggestion(BaseModel):
    user_id: int
    full_name: str
    score: float


class OcrLine(BaseModel):
    index: int
    image_index: int
    raw: str
    normalized: str
    status: str
    user_id: int | None
    score: float
    in_audience: bool
    suggestions: list[OcrSuggestion]


class OcrImportOut(BaseModel):
    id: int
    event_id: int | None
    engine: str
    image_count: int
    created_at: datetime
    committed_at: datetime | None
    detected_date: date | None
    date_text: str
    photo_date: date | None
    event: EventOut | None  # the chosen event
    suggested_events: list[EventOut]  # events on the detected (or photo) date
    lines: list[OcrLine]
    created_attendances: int  # saved from this import so far


class OcrImportUpdate(BaseModel):
    event_id: int


class OcrImportBrief(BaseModel):
    id: int
    event_id: int | None
    event_title: str | None
    engine: str
    image_count: int
    line_count: int
    created_at: datetime
    committed_at: datetime | None
    created_attendances: int


class OcrCommitEntry(BaseModel):
    user_id: int
    line_index: int | None = None  # which line (and so which photo) the entry came from


class OcrCommitIn(BaseModel):
    event_id: int | None = None  # defaults to the event chosen on the import
    entries: list[OcrCommitEntry] = Field(min_length=1)


class OcrCommitOut(BaseModel):
    created: int
    skipped_existing: int


# --- communication: shared audience -----------------------------------------
class AudienceIn(BaseModel):
    """Who receives an announcement or poll: every active user, or members of the given groups."""

    audience_all: bool = False
    group_ids: list[int] = Field(default=[], max_length=200)

    @model_validator(mode="after")
    def has_audience(self):
        self.group_ids = sorted(set(self.group_ids))
        if self.audience_all:
            self.group_ids = []
        elif not self.group_ids:
            raise ValueError("Choose at least one group, or send to everyone")
        return self


# --- announcements (newsletter) -----------------------------------------------
class AnnouncementIn(AudienceIn):
    title: str = Field(min_length=1, max_length=200)
    # Markdown: paragraphs, **bold**, *italic*, `code`, # headings, - / 1. lists, [links](https://…)
    body: str = Field(min_length=1, max_length=20_000)

    @model_validator(mode="after")
    def not_blank(self):
        self.title, self.body = self.title.strip(), self.body.strip()
        if not self.title or not self.body:
            raise ValueError("Title and message can't be blank")
        return self


class AnnouncementOut(BaseModel):
    id: int
    title: str
    body: str
    sent_at: datetime
    author_name: str
    audience_all: bool
    groups: list[GroupBrief]
    has_attachment: bool
    attachment_name: str | None
    attachment_type: str | None
    can_manage: bool = False
    # user view
    read_at: datetime | None = None
    # admin view
    recipient_count: int | None = None
    read_count: int | None = None


class InboxSummary(BaseModel):
    unread_announcements: int
    polls_to_vote: int


# --- polls ------------------------------------------------------------------
class PollIn(AudienceIn):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    options: list[str] = Field(min_length=2, max_length=8)
    closes_at: datetime
    is_anonymous: bool = True

    @field_validator("options")
    @classmethod
    def clean_options(cls, v: list[str]) -> list[str]:
        v = [o.strip() for o in v]
        if any(not o for o in v):
            raise ValueError("Options can't be blank")
        if any(len(o) > 200 for o in v):
            raise ValueError("Options can be at most 200 characters")
        if len({o.casefold() for o in v}) != len(v):
            raise ValueError("Each option must be different")
        return v

    @model_validator(mode="after")
    def clean(self):
        self.title, self.description = self.title.strip(), self.description.strip()
        if not self.title:
            raise ValueError("Title can't be blank")
        if self.closes_at.tzinfo is None:
            raise ValueError("closes_at must include a timezone offset")
        return self


class PollOptionOut(BaseModel):
    id: int
    label: str
    position: int
    votes: int | None = None  # null while results are hidden from this viewer
    percentage: float | None = None


class PollOut(BaseModel):
    id: int
    title: str
    description: str
    is_anonymous: bool
    status: str  # open | closed
    created_at: datetime
    closes_at: datetime
    closed_at: datetime | None
    author_name: str
    audience_all: bool
    groups: list[GroupBrief]
    options: list[PollOptionOut]
    results_visible: bool
    total_votes: int | None = None
    can_manage: bool = False
    # admin view
    eligible_count: int | None = None
    # user view
    has_voted: bool | None = None
    my_option_id: int | None = None


class VoteIn(BaseModel):
    option_id: int


class PollVoterOut(BaseModel):
    user_id: int
    full_name: str
    email: str
    voted: bool
    # Only for polls that aren't anonymous.
    voted_at: datetime | None = None
    option_id: int | None = None


class AnnouncementReaderOut(BaseModel):
    user_id: int
    full_name: str
    email: str
    read_at: datetime | None
