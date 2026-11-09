"""announcements (newsletter) and polls

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _user_fk(name: str = "created_by", ondelete: str = "SET NULL", nullable: bool = True):
    return sa.Column(name, sa.Integer, sa.ForeignKey("users.id", ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("audience_all", sa.Boolean, nullable=False),
        sa.Column("attachment_path", sa.String(300)),
        sa.Column("attachment_name", sa.String(255)),
        sa.Column("attachment_type", sa.String(50)),
        _user_fk(),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_announcements_created_by", "announcements", ["created_by"])
    op.create_index("ix_announcements_sent_at", "announcements", ["sent_at"])

    op.create_table(
        "announcement_groups",
        sa.Column("announcement_id", sa.Integer, sa.ForeignKey("announcements.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_id", sa.Integer, sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_announcement_groups_group_id", "announcement_groups", ["group_id"])

    op.create_table(
        "announcement_reads",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("announcement_id", sa.Integer, sa.ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False),
        _user_fk("user_id", "CASCADE", nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("announcement_id", "user_id", name="uq_announcement_read"),
    )
    op.create_index("ix_announcement_reads_announcement_id", "announcement_reads", ["announcement_id"])
    op.create_index("ix_announcement_reads_user_id", "announcement_reads", ["user_id"])

    op.create_table(
        "polls",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("is_anonymous", sa.Boolean, nullable=False),
        sa.Column("audience_all", sa.Boolean, nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        _user_fk(),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_polls_created_by", "polls", ["created_by"])

    op.create_table(
        "poll_groups",
        sa.Column("poll_id", sa.Integer, sa.ForeignKey("polls.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_id", sa.Integer, sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_poll_groups_group_id", "poll_groups", ["group_id"])

    op.create_table(
        "poll_options",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("poll_id", sa.Integer, sa.ForeignKey("polls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.UniqueConstraint("poll_id", "position", name="uq_poll_option_position"),
    )
    op.create_index("ix_poll_options_poll_id", "poll_options", ["poll_id"])

    op.create_table(
        "poll_votes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("poll_id", sa.Integer, sa.ForeignKey("polls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("option_id", sa.Integer, sa.ForeignKey("poll_options.id", ondelete="CASCADE"), nullable=False),
        _user_fk("user_id", "CASCADE", nullable=False),
        sa.Column("voted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("poll_id", "user_id", name="uq_poll_vote_user"),
    )
    op.create_index("ix_poll_votes_poll_id", "poll_votes", ["poll_id"])
    op.create_index("ix_poll_votes_option_id", "poll_votes", ["option_id"])
    op.create_index("ix_poll_votes_user_id", "poll_votes", ["user_id"])


def downgrade() -> None:
    for table in ("poll_votes", "poll_options", "poll_groups", "polls",
                  "announcement_reads", "announcement_groups", "announcements"):
        op.drop_table(table)
