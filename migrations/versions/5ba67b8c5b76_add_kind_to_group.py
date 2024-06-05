"""add kind to group

Revision ID: 5ba67b8c5b76
Revises: 17c42d14deb1
Create Date: 2024-05-25 15:29:57.726788

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ba67b8c5b76'
down_revision: Union[str, None] = '17c42d14deb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('groups', sa.Column('kind', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('groups', 'kind')
