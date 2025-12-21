"""Add deleted_at column for soft deletes

Revision ID: a23dd8e4cc01
Revises: 37b018c3c572
Create Date: 2025-12-20 23:01:32.123456

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a23dd8e4cc01"
down_revision: Union[str, Sequence[str], None] = "37b018c3c572"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add deleted_at column to all tables for soft delete functionality."""
    # Add deleted_at column to videos table
    op.add_column("videos", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    # Add deleted_at column to audio_files table
    op.add_column("audio_files", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    # Add deleted_at column to processing_jobs table
    op.add_column(
        "processing_jobs", sa.Column("deleted_at", sa.DateTime(), nullable=True)
    )

    # Add deleted_at column to notations table
    op.add_column("notations", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    # Add deleted_at column to drum_events table
    op.add_column("drum_events", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    # Create indexes on deleted_at columns for performance
    op.create_index("ix_videos_deleted_at", "videos", ["deleted_at"])
    op.create_index("ix_audio_files_deleted_at", "audio_files", ["deleted_at"])
    op.create_index("ix_processing_jobs_deleted_at", "processing_jobs", ["deleted_at"])
    op.create_index("ix_notations_deleted_at", "notations", ["deleted_at"])
    op.create_index("ix_drum_events_deleted_at", "drum_events", ["deleted_at"])


def downgrade() -> None:
    """Remove deleted_at columns and their indexes."""
    # Drop indexes first
    op.drop_index("ix_drum_events_deleted_at", table_name="drum_events")
    op.drop_index("ix_notations_deleted_at", table_name="notations")
    op.drop_index("ix_processing_jobs_deleted_at", table_name="processing_jobs")
    op.drop_index("ix_audio_files_deleted_at", table_name="audio_files")
    op.drop_index("ix_videos_deleted_at", table_name="videos")

    # Drop columns
    op.drop_column("drum_events", "deleted_at")
    op.drop_column("notations", "deleted_at")
    op.drop_column("processing_jobs", "deleted_at")
    op.drop_column("audio_files", "deleted_at")
    op.drop_column("videos", "deleted_at")
