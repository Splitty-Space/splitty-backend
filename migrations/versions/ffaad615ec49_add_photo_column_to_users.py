"""add photo column to users

Revision ID: ffaad615ec49
Revises: 4339a40970b0
Create Date: 2025-03-16 23:07:21.771215

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ffaad615ec49'
down_revision: Union[str, None] = '4339a40970b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('photo', sa.LargeBinary(), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'photo')
