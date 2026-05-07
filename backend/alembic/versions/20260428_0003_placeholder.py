"""Sync alembic revision present on some DB volumes (no schema change).

Revision ID: 20260428_0003
Revises: 20260425_0002
"""
from typing import Sequence, Union

revision: str = "20260428_0003"
down_revision: Union[str, None] = "20260425_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
