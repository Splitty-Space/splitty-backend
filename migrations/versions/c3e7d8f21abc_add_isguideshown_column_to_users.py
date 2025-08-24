from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3e7d8f21abc'
down_revision: Union[str, None] = '27e738f96eed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('isGuideShown', sa.Boolean(), nullable=True, server_default=sa.false()))
    op.alter_column('users', 'isGuideShown', existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    op.drop_column('users', 'isGuideShown')
