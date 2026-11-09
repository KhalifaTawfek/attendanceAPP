from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.audience import is_recipient, load_groups, recipients, recipients_query, visible_filter
from app.deps import DB, AdminUser, CurrentUser
from app.models import Announcement, AnnouncementRead, Poll, PollOption, Role, User, Vote, announcement_groups, poll_groups
from app.schemas import GroupBrief, InboxSummary, PollIn, PollOptionOut, PollOut, PollVoterOut, VoteIn
from app.timeutil import as_utc, now_utc

router = APIRouter(prefix="/polls", tags=["polls"])
inbox_router = APIRouter(prefix="/inbox", tags=["announcements", "polls"])

MAX_POLL_DAYS = 365


def is_open(p: Poll) -> bool:
    return p.closed_at is None and now_utc() < as_utc(p.closes_at)


def _out(db, p: Poll, viewer: User) -> PollOut:
    counts = dict(db.execute(
        select(Vote.option_id, func.count(Vote.id)).where(Vote.poll_id == p.id).group_by(Vote.option_id)).all())
    total = sum(counts.values())
    open_ = is_open(p)
    out = PollOut(
        id=p.id, title=p.title, description=p.description, is_anonymous=p.is_anonymous,
        status="open" if open_ else "closed", created_at=as_utc(p.created_at), closes_at=as_utc(p.closes_at),
        closed_at=as_utc(p.closed_at) if p.closed_at else None,
        author_name=p.author.full_name if p.author else "Former staff member",
        audience_all=p.audience_all, groups=[GroupBrief.model_validate(g) for g in p.groups],
        options=[], results_visible=False,
        can_manage=viewer.role == Role.admin and p.created_by == viewer.id,
    )
    if viewer.role == Role.admin:
        out.results_visible = True
        out.eligible_count = db.scalar(
            select(func.count()).select_from(recipients_query(p.audience_all, p.groups).subquery()))
    else:
        mine = db.scalar(select(Vote.option_id).where(Vote.poll_id == p.id, Vote.user_id == viewer.id))
        out.has_voted, out.my_option_id = mine is not None, mine
        # Users see results only once they've voted or the poll is closed, so early counts can't sway them.
        out.results_visible = mine is not None or not open_
    if out.results_visible:
        out.total_votes = total
    out.options = [
        PollOptionOut(
            id=o.id, label=o.label, position=o.position,
            votes=counts.get(o.id, 0) if out.results_visible else None,
            percentage=(round(100 * counts.get(o.id, 0) / total, 1) if total else 0.0) if out.results_visible else None,
        )
        for o in p.options
    ]
    return out


def _visible(db, poll_id: int, user: User) -> Poll:
    """Admins see every poll; users only polls aimed at them. Others get 404, so ids can't be probed."""
    p = db.get(Poll, poll_id)
    if p is None or (user.role != Role.admin and not is_recipient(user, p.audience_all, p.groups)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Poll not found")
    return p


def _managed(db, poll_id: int, admin: User) -> Poll:
    p = _visible(db, poll_id, admin)
    if p.created_by != admin.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the poll's author can manage it")
    return p


@router.post("", response_model=PollOut, status_code=201)
def create_poll(body: PollIn, admin: AdminUser, db: DB):
    """2–8 options, a deadline, and an audience. Anonymous unless `is_anonymous` is false."""
    closes_at = as_utc(body.closes_at)
    if closes_at <= now_utc():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The deadline must be in the future")
    if closes_at - now_utc() > timedelta(days=MAX_POLL_DAYS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"The deadline can be at most {MAX_POLL_DAYS} days away")
    p = Poll(
        title=body.title, description=body.description, is_anonymous=body.is_anonymous,
        audience_all=body.audience_all, groups=load_groups(db, body.group_ids), closes_at=closes_at,
        created_by=admin.id, options=[PollOption(label=label, position=i) for i, label in enumerate(body.options)],
    )
    db.add(p)
    db.commit()
    return _out(db, p, admin)


@router.get("", response_model=list[PollOut])
def list_polls(user: CurrentUser, db: DB, status_: str | None = Query(None, alias="status", pattern="^(open|closed)$"),
               group_id: int | None = None):
    """Open polls first (soonest deadline first), then closed ones (most recent first)."""
    stmt = select(Poll).order_by(Poll.created_at.desc()).limit(200)
    if user.role != Role.admin:
        stmt = stmt.where(visible_filter(Poll, poll_groups, "poll_id", user))
    if group_id is not None:
        stmt = stmt.where(Poll.id.in_(select(poll_groups.c.poll_id).where(poll_groups.c.group_id == group_id)))
    polls = list(db.scalars(stmt))
    if status_:
        polls = [p for p in polls if (status_ == "open") == is_open(p)]
    polls.sort(key=lambda p: (0, as_utc(p.closes_at).timestamp()) if is_open(p)
               else (1, -as_utc(p.closed_at or p.closes_at).timestamp()))
    return [_out(db, p, user) for p in polls]


@router.get("/{poll_id}", response_model=PollOut)
def get_poll(poll_id: int, user: CurrentUser, db: DB):
    """Admins always see live counts; users after voting or once the poll has closed."""
    return _out(db, _visible(db, poll_id, user), user)


@router.post("/{poll_id}/votes", response_model=PollOut, status_code=201)
def vote(poll_id: int, body: VoteIn, user: CurrentUser, db: DB):
    """Vote for exactly one option. Votes are final: they can't be changed or withdrawn."""
    if user.role == Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins can't vote")
    p = _visible(db, poll_id, user)
    if not is_open(p):
        raise HTTPException(status.HTTP_409_CONFLICT, "This poll is closed")
    if body.option_id not in {o.id for o in p.options}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "That option isn't part of this poll")
    if db.scalar(select(Vote.id).where(Vote.poll_id == p.id, Vote.user_id == user.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already voted in this poll")
    db.add(Vote(poll_id=p.id, option_id=body.option_id, user_id=user.id))
    try:
        db.commit()
    except IntegrityError:  # two requests raced past the check; the unique constraint keeps one
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already voted in this poll")
    return _out(db, p, user)


@router.post("/{poll_id}/close", response_model=PollOut)
def close_poll(poll_id: int, admin: AdminUser, db: DB):
    p = _managed(db, poll_id, admin)
    if not is_open(p):
        raise HTTPException(status.HTTP_409_CONFLICT, "This poll is already closed")
    p.closed_at = now_utc()
    db.commit()
    return _out(db, p, admin)


@router.get("/{poll_id}/voters", response_model=list[PollVoterOut])
def voters(poll_id: int, admin: AdminUser, db: DB):
    """Who has voted. For anonymous polls only yes/no: no choice, and no time either,
    because a vote time next to live counts would give the choice away."""
    p = _visible(db, poll_id, admin)
    votes = {v.user_id: v for v in db.scalars(select(Vote).where(Vote.poll_id == p.id))}
    people = {u.id: u for u in recipients(db, p.audience_all, p.groups)}
    # People who voted and later left the audience still count as having voted.
    for uid in set(votes) - set(people):
        if (u := db.get(User, uid)) is not None:
            people[uid] = u
    show = not p.is_anonymous
    return [
        PollVoterOut(
            user_id=u.id, full_name=u.full_name, email=u.email, voted=u.id in votes,
            voted_at=as_utc(votes[u.id].voted_at) if show and u.id in votes else None,
            option_id=votes[u.id].option_id if show and u.id in votes else None,
        )
        for u in sorted(people.values(), key=lambda u: (u.full_name.casefold(), u.id))
    ]


@router.delete("/{poll_id}", status_code=204)
def delete_poll(poll_id: int, admin: AdminUser, db: DB):
    db.delete(_managed(db, poll_id, admin))
    db.commit()


@inbox_router.get("", response_model=InboxSummary)
def inbox(user: CurrentUser, db: DB):
    """Counts for the navigation badges: unread announcements and open polls not yet voted on."""
    if user.role == Role.admin:
        return InboxSummary(unread_announcements=0, polls_to_vote=0)
    unread = db.scalar(select(func.count(Announcement.id)).where(
        visible_filter(Announcement, announcement_groups, "announcement_id", user),
        ~Announcement.id.in_(select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user.id)),
    ))
    candidates = db.scalars(select(Poll).where(
        visible_filter(Poll, poll_groups, "poll_id", user), Poll.closed_at.is_(None), Poll.closes_at > now_utc(),
        ~Poll.id.in_(select(Vote.poll_id).where(Vote.user_id == user.id)),
    ))
    return InboxSummary(unread_announcements=unread, polls_to_vote=sum(1 for p in candidates if is_open(p)))
