"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-20
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

user_role = sa.Enum("admin", "user", name="user_role")
attendance_status = sa.Enum("pending", "approved", "rejected", name="attendance_status")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_in_opens_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_in_closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("late_after_minutes", sa.Integer, nullable=False),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_events_starts_at", "events", ["starts_at"])

    op.create_table(
        "attendances",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("photo_path", sa.String(300), nullable=False),
        sa.Column("activity_summary", sa.Text, nullable=False),
        sa.Column("location_note", sa.String(200), nullable=False),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("declaration", sa.Boolean, nullable=False),
        sa.Column("is_late", sa.Boolean, nullable=False),
        sa.Column("status", attendance_status, nullable=False),
        sa.Column("review_comment", sa.Text, nullable=False),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "user_id", name="uq_attendance_event_user"),
    )
    op.create_index("ix_attendances_event_id", "attendances", ["event_id"])
    op.create_index("ix_attendances_user_id", "attendances", ["user_id"])
    op.create_index("ix_attendances_status", "attendances", ["status"])
    op.create_index("ix_attendances_submitted_at", "attendances", ["submitted_at"])


def downgrade() -> None:
    op.drop_table("attendances")
    op.drop_table("events")
    op.drop_table("users")
    attendance_status.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
