"""add recommended value to candidate_stage enum

Revision ID: b4be21c036ad
Revises: 9fabda6c6311
Create Date: 2026-08-21 14:52:45.882402

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4be21c036ad'
down_revision: Union[str, None] = '9fabda6c6311'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    # Postgres requires new enum values to be added outside a
    # transaction block in older versions, but modern Postgres (12+)
    # supports this within Alembic's transactional DDL. If this fails
    # with "unsafe use of new value" it means it was used in the same
    # transaction it was created in — not an issue here since we're
    # only adding the value, not using it yet.
    op.execute("ALTER TYPE candidate_stage ADD VALUE IF NOT EXISTS 'RECOMMENDED'")


def downgrade() -> None:
    # Postgres does not support removing a value from an enum type
    # directly — there's no ALTER TYPE ... DROP VALUE. A true downgrade
    # would require creating a new enum type without this value,
    # migrating every column over, and dropping the old type. Given
    # this is a purely additive change (a new valid value, not a
    # removal of anything), we deliberately leave downgrade as a no-op
    # rather than attempting a risky, disruptive type-swap.
    pass