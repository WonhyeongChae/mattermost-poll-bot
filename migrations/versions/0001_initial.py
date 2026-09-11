"""Create poll, option, and vote tables.

Revision ID: 0001_initial
Revises:
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "polls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("channel_id", sa.String(length=64), nullable=False),
        sa.Column("post_id", sa.String(length=64), nullable=True),
        sa.Column("creator_id", sa.String(length=64), nullable=False),
        sa.Column("question", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("action_token", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_token"),
        sa.UniqueConstraint("post_id"),
    )
    op.create_index("ix_polls_channel_id", "polls", ["channel_id"])
    op.create_index("ix_polls_creator_id", "polls", ["creator_id"])
    op.create_index("ix_polls_status", "polls", ["status"])

    op.create_table(
        "poll_options",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("poll_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["poll_id"], ["polls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_poll_options_poll_id", "poll_options", ["poll_id"])

    op.create_table(
        "votes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("poll_id", sa.String(length=36), nullable=False),
        sa.Column("option_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["option_id"], ["poll_options.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["poll_id"], ["polls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("poll_id", "user_id", name="uq_vote_poll_user"),
    )
    op.create_index("ix_votes_poll_id", "votes", ["poll_id"])
    op.create_index("ix_votes_user_id", "votes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_votes_user_id", table_name="votes")
    op.drop_index("ix_votes_poll_id", table_name="votes")
    op.drop_table("votes")
    op.drop_index("ix_poll_options_poll_id", table_name="poll_options")
    op.drop_table("poll_options")
    op.drop_index("ix_polls_status", table_name="polls")
    op.drop_index("ix_polls_creator_id", table_name="polls")
    op.drop_index("ix_polls_channel_id", table_name="polls")
    op.drop_table("polls")
