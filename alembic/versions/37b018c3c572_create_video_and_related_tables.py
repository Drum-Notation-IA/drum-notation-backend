"""Create video and related tables

Revision ID: 37b018c3c572
Revises: c5678901234b
Create Date: 2025-12-20 22:49:40.935409

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "37b018c3c572"
down_revision: Union[str, Sequence[str], None] = "c5678901234b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create videos table
    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create audio_files table
    op.create_table(
        "audio_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("channels", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create processing_jobs table
    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create notations table
    op.create_table(
        "notations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tempo", sa.Integer(), nullable=True),
        sa.Column("time_signature", sa.String(length=10), nullable=True),
        sa.Column(
            "notation_json", postgresql.JSON(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create drum_events table
    op.create_table(
        "drum_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audio_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("time_seconds", sa.Float(), nullable=False),
        sa.Column("instrument", sa.String(length=50), nullable=False),
        sa.Column("velocity", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("onset_time", sa.Float(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["audio_file_id"],
            ["audio_files.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for better performance
    op.create_index("ix_videos_user_id", "videos", ["user_id"])
    op.create_index("ix_videos_created_at", "videos", ["created_at"])
    op.create_index("ix_audio_files_video_id", "audio_files", ["video_id"])
    op.create_index("ix_processing_jobs_video_id", "processing_jobs", ["video_id"])
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"])
    op.create_index("ix_notations_video_id", "notations", ["video_id"])
    op.create_index("ix_drum_events_audio_file_id", "drum_events", ["audio_file_id"])
    op.create_index("ix_drum_events_time_seconds", "drum_events", ["time_seconds"])
    op.create_index("ix_drum_events_instrument", "drum_events", ["instrument"])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index("ix_drum_events_instrument", table_name="drum_events")
    op.drop_index("ix_drum_events_time_seconds", table_name="drum_events")
    op.drop_index("ix_drum_events_audio_file_id", table_name="drum_events")
    op.drop_index("ix_notations_video_id", table_name="notations")
    op.drop_index("ix_processing_jobs_status", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_video_id", table_name="processing_jobs")
    op.drop_index("ix_audio_files_video_id", table_name="audio_files")
    op.drop_index("ix_videos_created_at", table_name="videos")
    op.drop_index("ix_videos_user_id", table_name="videos")

    # Drop tables in reverse order (considering foreign key constraints)
    op.drop_table("drum_events")
    op.drop_table("notations")
    op.drop_table("processing_jobs")
    op.drop_table("audio_files")
    op.drop_table("videos")
