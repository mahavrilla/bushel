"""add staples + grocery_list_staples + staples_seeded

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-21 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'staples',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ingredient_id', sa.Integer(), nullable=False),
        sa.Column('auto_add', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ingredient_id'),
    )
    op.create_table(
        'grocery_list_staples',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('list_id', sa.Integer(), nullable=False),
        sa.Column('staple_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['list_id'], ['grocery_lists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staple_id'], ['staples.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('list_id', 'staple_id'),
    )
    op.add_column(
        'grocery_lists',
        sa.Column('staples_seeded', sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('grocery_lists', 'staples_seeded')
    op.drop_table('grocery_list_staples')
    op.drop_table('staples')
