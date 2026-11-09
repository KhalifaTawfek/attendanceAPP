from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.audience import is_recipient, load_groups, recipients, recipients_query, visible_filter
from app.config import get_settings
from app.deps import DB, AdminUser, CurrentUser
from app.models import Announcement, AnnouncementRead, Role, User, announcement_groups
from app.schemas import AnnouncementIn, AnnouncementOut, AnnouncementReaderOut, GroupBrief
from app.storage import delete_photo, photo_abspath, read_upload_limited, store_document
from app.timeutil import as_utc

router = APIRouter(prefix="/announcements", tags=["announcements"])


def _out(db, a: Announcement, viewer: User) -> AnnouncementOut:
    out = AnnouncementOut(
        id=a.id, title=a.title, body=a.body, sent_at=as_utc(a.sent_at),
        author_name=a.author.full_name if a.author else "Former staff member",
        audience_all=a.audience_all, groups=[GroupBrief.model_validate(g) for g in a.groups],
        has_attachment=a.attachment_path is not None,
        attachment_name=a.attachment_name, attachment_type=a.attachment_type,
        can_manage=viewer.role == Role.admin and a.created_by == viewer.id,
    )
    if viewer.role == Role.admin:
        audience = recipients_query(a.audience_all, a.groups).subquery()
        out.recipient_count = db.scalar(select(func.count()).select_from(audience))
        out.read_count = db.scalar(
            select(func.count(AnnouncementRead.id)).where(
                AnnouncementRead.announcement_id == a.id, AnnouncementRead.user_id.in_(select(audience.c.id))
            )
        )
    else:
        read_at = db.scalar(select(AnnouncementRead.read_at).where(
            AnnouncementRead.announcement_id == a.id, AnnouncementRead.user_id == viewer.id))
        out.read_at = as_utc(read_at) if read_at else None
    return out


def _visible(db, announcement_id: int, user: User) -> Announcement:
    """Admins see every announcement; users only the ones sent to them. Others get 404."""
    a = db.get(Announcement, announcement_id)
    if a is None or (user.role != Role.admin and not is_recipient(user, a.audience_all, a.groups)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found")
    return a


def _managed(db, announcement_id: int, admin: User) -> Announcement:
    a = _visible(db, announcement_id, admin)
    if a.created_by != admin.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author can change this announcement")
    return a


@router.post("", response_model=AnnouncementOut, status_code=201)
def send_announcement(body: AnnouncementIn, admin: AdminUser, db: DB):
    """Send to everyone (`audience_all`) or to the members of one or more groups."""
    a = Announcement(title=body.title, body=body.body, audience_all=body.audience_all,
                     groups=load_groups(db, body.group_ids), created_by=admin.id)
    db.add(a)
    db.commit()
    return _out(db, a, admin)


@router.get("", response_model=list[AnnouncementOut])
def list_announcements(user: CurrentUser, db: DB, unread: bool = False, group_id: int | None = None):
    """Newest first. Admins get every announcement; users get the ones sent to them."""
    stmt = select(Announcement).order_by(Announcement.sent_at.desc(), Announcement.id.desc()).limit(200)
    if user.role != Role.admin:
        stmt = stmt.where(visible_filter(Announcement, announcement_groups, "announcement_id", user))
        if unread:
            stmt = stmt.where(~Announcement.id.in_(
                select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user.id)))
    if group_id is not None:
        stmt = stmt.where(Announcement.id.in_(
            select(announcement_groups.c.announcement_id).where(announcement_groups.c.group_id == group_id)))
    return [_out(db, a, user) for a in db.scalars(stmt)]


@router.get("/{announcement_id}", response_model=AnnouncementOut)
def get_announcement(announcement_id: int, user: CurrentUser, db: DB):
    return _out(db, _visible(db, announcement_id, user), user)


@router.post("/{announcement_id}/read", response_model=AnnouncementOut)
def mark_read(announcement_id: int, user: CurrentUser, db: DB):
    """Idempotent; keeps the first read time."""
    if user.role == Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only recipients can mark announcements read")
    a = _visible(db, announcement_id, user)
    exists = db.scalar(select(AnnouncementRead.id).where(
        AnnouncementRead.announcement_id == a.id, AnnouncementRead.user_id == user.id))
    if not exists:
        db.add(AnnouncementRead(announcement_id=a.id, user_id=user.id))
        try:
            db.commit()
        except IntegrityError:  # another tab got there first
            db.rollback()
    return _out(db, a, user)


@router.get("/{announcement_id}/readers", response_model=list[AnnouncementReaderOut])
def readers(announcement_id: int, admin: AdminUser, db: DB):
    """Every recipient and whether (and when) they opened it."""
    a = _visible(db, announcement_id, admin)
    reads = {r.user_id: r.read_at for r in db.scalars(
        select(AnnouncementRead).where(AnnouncementRead.announcement_id == a.id))}
    return [
        AnnouncementReaderOut(user_id=u.id, full_name=u.full_name, email=u.email,
                              read_at=as_utc(reads[u.id]) if u.id in reads else None)
        for u in recipients(db, a.audience_all, a.groups)
    ]


@router.post("/{announcement_id}/attachment", response_model=AnnouncementOut)
def upload_attachment(announcement_id: int, admin: AdminUser, db: DB, file: Annotated[UploadFile, File()]):
    """Attach or replace one PDF or image (images are re-encoded and stripped of metadata)."""
    a = _managed(db, announcement_id, admin)
    s = get_settings()
    rel, content_type = store_document(read_upload_limited(file, s.max_upload_mb), s.max_image_px)
    old = a.attachment_path
    a.attachment_path, a.attachment_type = rel, content_type
    name = (file.filename or "attachment").replace("\\", "/").rsplit("/", 1)[-1][:200]
    if content_type == "image/jpeg" and not name.lower().endswith((".jpg", ".jpeg")):
        name = name.rsplit(".", 1)[0] + ".jpg"
    a.attachment_name = name
    db.commit()
    if old:
        delete_photo(old)
    return _out(db, a, admin)


@router.get("/{announcement_id}/attachment")
def download_attachment(announcement_id: int, user: CurrentUser, db: DB):
    a = _visible(db, announcement_id, user)
    if not a.attachment_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    path = photo_abspath(a.attachment_path)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    return FileResponse(
        path, media_type=a.attachment_type, filename=a.attachment_name,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{announcement_id}", status_code=204)
def delete_announcement(announcement_id: int, admin: AdminUser, db: DB):
    a = _managed(db, announcement_id, admin)
    path = a.attachment_path
    db.delete(a)
    db.commit()
    if path:
        delete_photo(path)
