"""add updated_at to roles

Revision ID: c5678901234b
Revises: b1234567890a
Create Date: 2025-12-20 10:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5678901234b"
down_revision: Union[str, Sequence[str], None] = "b1234567890a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add updated_at column to roles table
    op.add_column(
        "roles",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Also add updated_at and deleted_at columns to user_roles table if they don't exist
    op.add_column(
        "user_roles",
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "user_roles",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "user_roles",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the added columns
    op.drop_column("user_roles", "deleted_at")
    op.drop_column("user_roles", "updated_at")
    op.drop_column("user_roles", "created_at")
    op.drop_column("roles", "updated_at")
