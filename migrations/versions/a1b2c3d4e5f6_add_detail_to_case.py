"""add detail to case

Revision ID: a1b2c3d4e5f6
Revises: 8b730e8d5d54
Create Date: 2026-07-02 09:57:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '8b730e8d5d54'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('cases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('detail', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('cases', schema=None) as batch_op:
        batch_op.drop_column('detail')
