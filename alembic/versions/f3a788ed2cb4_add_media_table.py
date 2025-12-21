"""Add media table

Revision ID: f3a788ed2cb4
Revises: c5678901234b
Create Date: 2025-12-20 20:08:34.023027

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a788ed2cb4'
down_revision: Union[str, Sequence[str], None] = 'c5678901234b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
