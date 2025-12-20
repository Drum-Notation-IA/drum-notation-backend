"""add roles and user_roles tables

Revision ID: b1234567890a
Revises: a630460b5dcd
Create Date: 2025-12-19 10:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1234567890a"
down_revision: Union[str, Sequence[str], None] = "a630460b5dcd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create roles table
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)

    # Create user_roles table
    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    # Insert default roles
    roles_table = sa.table(
        "roles",
        sa.column("id", postgresql.UUID),
        sa.column("name", sa.Text),
        sa.column("description", sa.Text),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    import uuid
    from datetime import datetime

    now = datetime.utcnow()

    op.bulk_insert(
        roles_table,
        [
            {
                "id": uuid.uuid4(),
                "name": "user",
                "description": "Default user role with basic permissions",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": uuid.uuid4(),
                "name": "admin",
                "description": "Administrator role with full permissions",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": uuid.uuid4(),
                "name": "premium",
                "description": "Premium user role with extended permissions",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop user_roles table first (due to foreign key constraints)
    op.drop_table("user_roles")

    # Drop roles table
    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_table("roles")
