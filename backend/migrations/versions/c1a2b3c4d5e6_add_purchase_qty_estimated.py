"""add purchase_qty_estimated to grocery_list_items

Revision ID: c1a2b3c4d5e6
Revises: 0cff1d550060
Create Date: 2026-06-20 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = '0cff1d550060'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'grocery_list_items',
        sa.Column('purchase_qty_estimated', sa.Boolean(), server_default='false', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('grocery_list_items', 'purchase_qty_estimated')
