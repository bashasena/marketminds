"""daily_snapshots: market_id for multi-market storage

Revision ID: 20260425_0002
Revises: 20260420_0001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260425_0002"
down_revision: Union[str, None] = "20260420_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("daily_snapshots", sa.Column("market_id", sa.String(length=32), server_default="in_nifty", nullable=False))
    op.drop_constraint("uq_daily_snapshots_date", "daily_snapshots", type_="unique")
    op.create_unique_constraint("uq_daily_snapshots_date_market", "daily_snapshots", ["snapshot_date", "market_id"])
    op.create_index(op.f("ix_daily_snapshots_market_id"), "daily_snapshots", ["market_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_daily_snapshots_market_id"), table_name="daily_snapshots")
    op.drop_constraint("uq_daily_snapshots_date_market", "daily_snapshots", type_="unique")
    op.create_unique_constraint("uq_daily_snapshots_date", "daily_snapshots", ["snapshot_date"])
    op.drop_column("daily_snapshots", "market_id")
