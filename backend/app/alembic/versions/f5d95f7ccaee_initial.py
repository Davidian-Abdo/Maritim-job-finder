"""initial

Revision ID: f5d95f7ccaee
Revises: 93a23bc9a0ca
Create Date: 2026-02-12 20:54:56.128744

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5d95f7ccaee'
down_revision: Union[str, Sequence[str], None] = '93a23bc9a0ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
