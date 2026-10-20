import csv
import io
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from app.deps import DB, AdminUser
from app.metrics import attendance_reviews
from app.models import Attendance, AttendanceStatus, Event, Group, Role, User
from app.routers.auth import find_user_by_email
from app.routers.events import get_event_or_404
from app.schemas import (
    AttendanceOut,
    AttendancePage,
    AttendanceReview,
    GroupIn,
    GroupOut,
    GroupUpdate,
    StatsOut,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.security import hash_password
from app.timeutil import as_utc, now_utc

router = APIRouter(prefix="/admin", tags=["admin"])


# --- users -----------------------------------------------------------------
@router.get("/users", response_model=list[UserOut])
def list_users(_: AdminUser, db: DB, q: str | None = None, include_inactive: bool = True):
    stmt = select(User).order_by(User.full_name)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.full_name).like(like), func.lower(User.email).like(like)))
    if not include_inactive:
        stmt = stmt.where(User.is_active.is_(True))
    return db.scalars(stmt).all()


@router.post("/users", response_model=UserOut, status_code=201)
def enroll_user(body: UserCreate, _: AdminUser, db: DB):
    if find_user_by_email(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=body.email.lower(), full_name=body.full_name,
        password_hash=hash_password(body.password), role=body.role,
    )
    db.add(user)
    db.commit()
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, admin: AdminUser, db: DB):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    data = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (data.get("is_active") is False or data.get("role") == Role.user):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot demote or deactivate yourself")
    if (pw := data.pop("password", None)) is not None:
        user.password_hash = hash_password(pw)
    for k, v in data.items():
        if v is not None:
            setattr(user, k, v)
    db.commit()
    return user


# --- groups ------------------------------------------------------------------
def _group_out(g: Group) -> GroupOut:
    return GroupOut(id=g.id, name=g.name, description=g.description, created_at=g.created_at,
                    member_ids=[m.id for m in g.members])


def _members(db, ids: list[int]) -> list[User]:
    users = db.scalars(select(User).where(User.id.in_(ids))).all() if ids else []
    if len(users) != len(set(ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown user id")
    return list(users)


def _name_taken(db, name: str, exclude_id: int | None = None) -> bool:
    stmt = select(Group.id).where(func.lower(Group.name) == name.lower())
    if exclude_id:
        stmt = stmt.where(Group.id != exclude_id)
    return db.scalar(stmt) is not None


@router.get("/groups", response_model=list[GroupOut])
def list_groups(_: AdminUser, db: DB):
    return [_group_out(g) for g in db.scalars(select(Group).order_by(Group.name))]


@router.post("/groups", response_model=GroupOut, status_code=201)
def create_group(body: GroupIn, _: AdminUser, db: DB):
    if _name_taken(db, body.name):
        raise HTTPException(status.HTTP_409_CONFLICT, "A group with this name already exists")
    g = Group(name=body.name, description=body.description, members=_members(db, body.member_ids))
    db.add(g)
    db.commit()
    return _group_out(g)


@router.patch("/groups/{group_id}", response_model=GroupOut)
def update_group(group_id: int, body: GroupUpdate, _: AdminUser, db: DB):
    g = db.get(Group, group_id)
    if g is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    if body.name is not None:
        if _name_taken(db, body.name, exclude_id=g.id):
            raise HTTPException(status.HTTP_409_CONFLICT, "A group with this name already exists")
        g.name = body.name
    if body.description is not None:
        g.description = body.description
    if body.member_ids is not None:
        g.members = _members(db, body.member_ids)
    db.commit()
    return _group_out(g)


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int, _: AdminUser, db: DB):
    g = db.get(Group, group_id)
    if g is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    db.delete(g)
    db.commit()


# --- attendances -------------------------------------------------------------
class AttendanceFilters:
    def __init__(
        self,
        event_id: int | None = None,
        user_id: int | None = None,
        group_id: int | None = None,
        status_: Annotated[AttendanceStatus | None, Query(alias="status")] = None,
        is_late: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        q: str | None = None,
        sort: str = Query("-submitted_at", pattern="^-?(submitted_at|user|event|status)$"),
    ):
        self.event_id, self.user_id, self.status, self.is_late = event_id, user_id, status_, is_late
        self.group_id = group_id
        self.date_from, self.date_to, self.q, self.sort = date_from, date_to, q, sort

    def apply(self, stmt):
        stmt = stmt.join(Attendance.user).join(Attendance.event)
        if self.event_id:
            stmt = stmt.where(Attendance.event_id == self.event_id)
        if self.user_id:
            stmt = stmt.where(Attendance.user_id == self.user_id)
        if self.group_id:
            stmt = stmt.where(User.groups.any(Group.id == self.group_id))
        if self.status:
            stmt = stmt.where(Attendance.status == self.status)
        if self.is_late is not None:
            stmt = stmt.where(Attendance.is_late.is_(self.is_late))
        if self.date_from:
            stmt = stmt.where(Attendance.submitted_at >= self.date_from)
        if self.date_to:
            stmt = stmt.where(Attendance.submitted_at <= self.date_to)
        if self.q:
            like = f"%{self.q.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.full_name).like(like),
                    func.lower(User.email).like(like),
                    func.lower(Event.title).like(like),
                )
            )
        return stmt

    def order(self, stmt):
        col = {
            "submitted_at": Attendance.submitted_at,
            "user": User.full_name,
            "event": Event.title,
            "status": Attendance.status,
        }[self.sort.lstrip("-")]
        return stmt.order_by(col.desc() if self.sort.startswith("-") else col.asc(), Attendance.id.desc())


Filters = Annotated[AttendanceFilters, Depends()]


@router.get("/attendances", response_model=AttendancePage)
def list_attendances(
    _: AdminUser,
    db: DB,
    f: Filters,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    base = f.apply(select(Attendance))
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    stmt = (
        f.order(base)
        .options(joinedload(Attendance.user), joinedload(Attendance.event))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return AttendancePage(items=db.scalars(stmt).all(), total=total or 0, page=page, page_size=page_size)


@router.patch("/attendances/{attendance_id}", response_model=AttendanceOut)
def review_attendance(attendance_id: int, body: AttendanceReview, admin: AdminUser, db: DB):
    att = db.get(Attendance, attendance_id)
    if att is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attendance not found")
    att.status = body.status
    att.review_comment = body.review_comment
    att.reviewed_by = admin.id
    att.reviewed_at = now_utc()
    db.commit()
    attendance_reviews.labels(status=body.status.value).inc()
    db.refresh(att)
    return att


EXPORT_COLUMNS = [
    "ID", "Event", "Event start (UTC)", "User", "Email", "Submitted at (UTC)", "Late",
    "Status", "Activity summary", "Location note", "Review comment",
]


def _export_rows(atts: list[Attendance]):
    for a in atts:
        yield [
            a.id, a.event.title, as_utc(a.event.starts_at).strftime("%Y-%m-%d %H:%M"),
            a.user.full_name, a.user.email, as_utc(a.submitted_at).strftime("%Y-%m-%d %H:%M:%S"),
            "yes" if a.is_late else "no", a.status.value, a.activity_summary, a.location_note,
            a.review_comment,
        ]


@router.get("/attendances/export")
def export_attendances(_: AdminUser, db: DB, f: Filters, format: str = Query("csv", pattern="^(csv|xlsx)$")):
    stmt = f.order(f.apply(select(Attendance))).options(
        joinedload(Attendance.user), joinedload(Attendance.event)
    )
    atts = db.scalars(stmt).all()
    stamp = now_utc().strftime("%Y%m%d-%H%M%S")

    if format == "csv":
        buf = io.StringIO()
        buf.write("﻿")  # BOM so Excel detects UTF-8
        writer = csv.writer(buf)
        writer.writerow(EXPORT_COLUMNS)
        writer.writerows(_export_rows(atts))
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="attendances-{stamp}.csv"'},
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendances"
    ws.append(EXPORT_COLUMNS)
    for row in _export_rows(atts):
        ws.append(row)
    ws.freeze_panes = "A2"
    for col, width in zip("ABCDEFGHIJK", [6, 30, 18, 24, 30, 20, 6, 10, 50, 24, 30]):
        ws.column_dimensions[col].width = width
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return StreamingResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="attendances-{stamp}.xlsx"'},
    )


# --- stats / absentees ---------------------------------------------------------
def expected_users(event: Event):
    """Active non-admin users expected at an event: its groups' members, or everyone."""
    stmt = select(User).where(User.is_active.is_(True), User.role == Role.user)
    if event.groups:
        stmt = stmt.where(User.groups.any(Group.id.in_([g.id for g in event.groups])))
    return stmt


@router.get("/stats", response_model=StatsOut)
def stats(_: AdminUser, db: DB):
    by_status = dict(db.execute(select(Attendance.status, func.count()).group_by(Attendance.status)).all())
    active_users = db.scalar(select(func.count()).where(User.is_active.is_(True), User.role == Role.user)) or 0
    recent = db.scalars(select(Event).order_by(Event.starts_at.desc()).limit(8)).all()
    counts = dict(db.execute(
        select(Attendance.event_id, func.count())
        .where(Attendance.event_id.in_([e.id for e in recent]))
        .group_by(Attendance.event_id)
    ).all())
    return StatsOut(
        total_users=active_users,
        total_events=db.scalar(select(func.count(Event.id))) or 0,
        total_attendances=sum(by_status.values()),
        pending=by_status.get(AttendanceStatus.pending, 0),
        approved=by_status.get(AttendanceStatus.approved, 0),
        rejected=by_status.get(AttendanceStatus.rejected, 0),
        late=db.scalar(select(func.count()).where(Attendance.is_late.is_(True))) or 0,
        upcoming_events=db.scalar(select(func.count()).where(Event.starts_at > now_utc())) or 0,
        recent_events=[
            {"id": e.id, "title": e.title, "starts_at": as_utc(e.starts_at).isoformat(),
             "attendances": counts.get(e.id, 0),
             "expected": db.scalar(select(func.count()).select_from(expected_users(e).subquery())) or 0,
             "groups": [g.name for g in e.groups]}
            for e in recent
        ],
    )


@router.get("/events/{event_id}/absentees", response_model=list[UserOut])
def absentees(event_id: int, _: AdminUser, db: DB):
    event = get_event_or_404(db, event_id)
    present = select(Attendance.user_id).where(Attendance.event_id == event_id)
    stmt = expected_users(event).where(User.id.not_in(present)).order_by(User.full_name)
    return db.scalars(stmt).all()
