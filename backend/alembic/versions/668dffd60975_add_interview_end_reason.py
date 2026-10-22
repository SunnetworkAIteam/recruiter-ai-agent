"""add_interview_end_reason

Revision ID: 668dffd60975
Revises: b2c3d4e5f6a7
Create Date: ...
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '668dffd60975'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('interviews', sa.Column('end_reason_raw', sa.String(), nullable=True))
    op.add_column('interviews', sa.Column('end_reason_category', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('interviews', 'end_reason_category')
    op.drop_column('interviews', 'end_reason_raw')