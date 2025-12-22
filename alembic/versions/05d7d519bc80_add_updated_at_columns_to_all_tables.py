"""add_updated_at_columns_to_all_tables

Revision ID: 05d7d519bc80
Revises: a23dd8e4cc01
Create Date: 2025-12-21 15:37:34.295360

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "05d7d519bc80"
down_revision: Union[str, Sequence[str], None] = "a23dd8e4cc01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add updated_at columns to all tables that extend BaseModel."""
    # Add updated_at column to users table
    op.add_column(
        "users",
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # Add updated_at column to roles table
    op.add_column(
        "roles",
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # Add updated_at column to user_roles table
    op.add_column(
        "user_roles",
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # Add updated_at column to videos table
    op.add_column(
        "videos",
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # Add updated_at column to audio_files table
    op.add_column(
        "audio_files",
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # Add updated_at column to processing_jobs table
    op.add_column(
        "processing_jobs",
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # Add updated_at column to notations table
    op.add_column(
        "notations",
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # Add updated_at column to drum_events table
    op.add_column(
        "drum_events",
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
    )


def downgrade() -> None:
    """Remove updated_at columns from all tables."""
    # Drop updated_at columns
    op.drop_column("drum_events", "updated_at")
    op.drop_column("notations", "updated_at")
    op.drop_column("processing_jobs", "updated_at")
    op.drop_column("audio_files", "updated_at")
    op.drop_column("videos", "updated_at")
    op.drop_column("user_roles", "updated_at")
    op.drop_column("roles", "updated_at")
    op.drop_column("users", "updated_at")
