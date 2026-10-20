from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.deps import DB, CurrentUser
from app.metrics import attendance_submissions
from app.models import Attendance, Role
from app.routers.events import can_attend, get_event_or_404, is_check_in_open
from app.schemas import AttendanceOut
from app.storage import delete_photo, photo_abspath, save_photo
from app.timeutil import as_utc, now_utc

router = APIRouter(prefix="/attendances", tags=["attendances"])


@router.post("", response_model=AttendanceOut, status_code=201)
async def submit_attendance(
    user: CurrentUser,
    db: DB,
    event_id: Annotated[int, Form()],
    activity_summary: Annotated[str, Form(min_length=3, max_length=2000)],
    declaration: Annotated[bool, Form()],
    photo: Annotated[UploadFile, File()],
    location_note: Annotated[str, Form(max_length=200)] = "",
):
    event = get_event_or_404(db, event_id)
    if not can_attend(user, event):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This event is limited to specific groups")
    if not declaration:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "You must confirm the presence declaration")
    if not is_check_in_open(event):
        raise HTTPException(status.HTTP_409_CONFLICT, "Check-in for this event is not open")
    existing = db.scalar(
        select(Attendance.id).where(Attendance.event_id == event.id, Attendance.user_id == user.id)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already submitted attendance for this event")

    photo_path = await save_photo(photo)
    now = now_utc()
    is_late = now > as_utc(event.starts_at) + timedelta(minutes=event.late_after_minutes)
    att = Attendance(
        event_id=event.id,
        user_id=user.id,
        photo_path=photo_path,
        activity_summary=activity_summary.strip(),
        location_note=location_note.strip(),
        declaration=True,
        is_late=is_late,
        submitted_at=now,
    )
    db.add(att)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        delete_photo(photo_path)
        raise HTTPException(status.HTTP_409_CONFLICT, "You already submitted attendance for this event")
    attendance_submissions.labels(late=str(is_late).lower()).inc()
    db.refresh(att)
    return att


@router.get("/me", response_model=list[AttendanceOut])
def my_attendances(user: CurrentUser, db: DB):
    stmt = (
        select(Attendance)
        .options(joinedload(Attendance.user), joinedload(Attendance.event))
        .where(Attendance.user_id == user.id)
        .order_by(Attendance.submitted_at.desc())
    )
    return db.scalars(stmt).all()


@router.get("/{attendance_id}/photo", response_class=FileResponse)
def get_photo(attendance_id: int, user: CurrentUser, db: DB):
    att = db.get(Attendance, attendance_id)
    if att is None or (user.role != Role.admin and att.user_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    path = photo_abspath(att.photo_path)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
