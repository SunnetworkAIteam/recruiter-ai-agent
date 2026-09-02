"""add candidate round_status

Revision ID: a1b2c3d4e5f6
Revises: b4be21c036ad
Create Date: 2026-09-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'b4be21c036ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    round_status_enum = sa.Enum(
        "selected_r1", "selected_r2", "hired", "rejected",
        name="candidate_round_status",
    )
    round_status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "candidates",
        sa.Column("round_status", round_status_enum, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidates", "round_status")
    sa.Enum(name="candidate_round_status").drop(op.get_bind(), checkfirst=True)