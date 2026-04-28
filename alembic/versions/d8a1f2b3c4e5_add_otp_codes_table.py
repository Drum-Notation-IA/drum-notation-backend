"""add otp_codes table for 2FA

Revision ID: d8a1f2b3c4e5
Revises: 05d7d519bc80
Create Date: 2026-04-27 13:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8a1f2b3c4e5"
down_revision: Union[str, Sequence[str], None] = "05d7d519bc80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create otp_codes table for 2FA challenge tracking."""
    op.create_table(
        "otp_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "purpose",
            sa.String(length=32),
            nullable=False,
            server_default="login",
        ),
        sa.Column(
            "challenge_token_hash", sa.String(length=128), nullable=False
        ),
        sa.Column("otp_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("5"),
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "challenge_token_hash", name="uq_otp_codes_challenge_token_hash"
        ),
    )

    # Hot-path indexes
    op.create_index(
        "ix_otp_codes_user_id", "otp_codes", ["user_id"], unique=False
    )
    op.create_index(
        "ix_otp_codes_challenge_token_hash",
        "otp_codes",
        ["challenge_token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_otp_codes_expires_at", "otp_codes", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_otp_codes_deleted_at", "otp_codes", ["deleted_at"], unique=False
    )


def downgrade() -> None:
    """Drop otp_codes table and its indexes."""
    op.drop_index("ix_otp_codes_deleted_at", table_name="otp_codes")
    op.drop_index("ix_otp_codes_expires_at", table_name="otp_codes")
    op.drop_index(
        "ix_otp_codes_challenge_token_hash", table_name="otp_codes"
    )
    op.drop_index("ix_otp_codes_user_id", table_name="otp_codes")
    op.drop_table("otp_codes")
