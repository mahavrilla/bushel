"""add price_cache

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'price_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kroger_upc', sa.String(length=50), nullable=False),
        sa.Column('location_id', sa.String(length=50), nullable=False),
        sa.Column('regular_cents', sa.Integer(), nullable=True),
        sa.Column('promo_cents', sa.Integer(), nullable=True),
        sa.Column('size_text', sa.String(length=100), nullable=True),
        sa.Column('stock_level', sa.String(length=40), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('kroger_upc', 'location_id', name='uq_price_cache_upc_loc'),
    )


def downgrade() -> None:
    op.drop_table('price_cache')
