"""user groups, recurring events, drop GPS columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-20
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

frequency = sa.Enum("daily", "weekly", "monthly", name="recurrence_frequency")


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "group_members",
        sa.Column("group_id", sa.Integer, sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"])

    op.create_table(
        "event_series",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("frequency", frequency, nullable=False),
        sa.Column("interval", sa.Integer, nullable=False),
        sa.Column("weekdays", sa.String(20), nullable=False),
        sa.Column("until", sa.Date),
        sa.Column("count", sa.Integer),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("series_id", sa.Integer, nullable=True))
        b.create_foreign_key("fk_events_series_id", "event_series", ["series_id"], ["id"], ondelete="SET NULL")
        b.create_index("ix_events_series_id", ["series_id"])

    op.create_table(
        "event_groups",
        sa.Column("event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_id", sa.Integer, sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_event_groups_group_id", "event_groups", ["group_id"])

    with op.batch_alter_table("attendances") as b:
        b.drop_column("latitude")
        b.drop_column("longitude")


def downgrade() -> None:
    with op.batch_alter_table("attendances") as b:
        b.add_column(sa.Column("latitude", sa.Float))
        b.add_column(sa.Column("longitude", sa.Float))
    op.drop_table("event_groups")
    with op.batch_alter_table("events") as b:
        b.drop_index("ix_events_series_id")
        b.drop_constraint("fk_events_series_id", type_="foreignkey")
        b.drop_column("series_id")
    op.drop_table("event_series")
    frequency.drop(op.get_bind(), checkfirst=True)
    op.drop_table("group_members")
    op.drop_table("groups")
