"""Who an announcement or poll is for.

An item targets either every active user (`audience_all`) or the members of its groups.
Admins (professors) send; users (students) receive. Membership is evaluated live, so someone
added to a group later also sees what was sent to it, and someone removed loses access.
"""

from fastapi import HTTPException, status
from sqlalchemy import or_, select

from app.models import Group, Role, User, group_members


def load_groups(db, ids: list[int]) -> list[Group]:
    groups = db.scalars(select(Group).where(Group.id.in_(ids))).all() if ids else []
    if len(groups) != len(set(ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown group id")
    return sorted(groups, key=lambda g: g.name.casefold())


def recipients_query(audience_all: bool, groups: list[Group]):
    """SELECT of the active users the item is for."""
    stmt = select(User).where(User.role == Role.user, User.is_active.is_(True))
    if not audience_all:
        member_ids = select(group_members.c.user_id).where(group_members.c.group_id.in_([g.id for g in groups]))
        stmt = stmt.where(User.id.in_(member_ids))
    return stmt


def recipients(db, audience_all: bool, groups: list[Group]) -> list[User]:
    return list(db.scalars(recipients_query(audience_all, groups).order_by(User.full_name, User.id)))


def is_recipient(user: User, audience_all: bool, groups: list[Group]) -> bool:
    if user.role != Role.user or not user.is_active:
        return False
    return audience_all or bool({g.id for g in groups} & {g.id for g in user.groups})


def visible_filter(model, link_table, link_column: str, user: User):
    """SQL filter on `model` for items this user receives."""
    group_ids = [g.id for g in user.groups]
    linked = select(getattr(link_table.c, link_column)).where(link_table.c.group_id.in_(group_ids))
    return or_(model.audience_all.is_(True), model.id.in_(linked))
