"""initial tables

Revision ID: 20260420_0001
Revises:
Create Date: 2026-04-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260420_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("composite_sentiment", sa.Float(), nullable=True),
        sa.Column("nifty_close", sa.Float(), nullable=True),
        sa.Column("nifty_pct_change", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_date", name="uq_daily_snapshots_date"),
    )
    op.create_index(op.f("ix_daily_snapshots_snapshot_date"), "daily_snapshots", ["snapshot_date"], unique=False)

    op.create_table(
        "fii_dii_flows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("flow_date", sa.Date(), nullable=False),
        sa.Column("fii_net_crores", sa.Float(), nullable=True),
        sa.Column("dii_net_crores", sa.Float(), nullable=True),
        sa.Column("raw_note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flow_date", name="uq_fii_dii_flow_date"),
    )
    op.create_index(op.f("ix_fii_dii_flows_flow_date"), "fii_dii_flows", ["flow_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fii_dii_flows_flow_date"), table_name="fii_dii_flows")
    op.drop_table("fii_dii_flows")
    op.drop_index(op.f("ix_daily_snapshots_snapshot_date"), table_name="daily_snapshots")
    op.drop_table("daily_snapshots")
