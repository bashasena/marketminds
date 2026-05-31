"""Add volume_watchlist and app_settings tables

Revision ID: 20260531_0004
Revises: 20260428_0003
Create Date: 2026-05-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260531_0004"
down_revision: Union[str, None] = "20260428_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "volume_watchlist",
        sa.Column("sym", sa.String(20), primary_key=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False, server_default=""),
        sa.Column("last_crossed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_ratio", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_avg30", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_cur_vol", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_pcr", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("last_oi_trend", sa.String(20), nullable=False, server_default="Flat"),
        sa.Column("last_signal", sa.String(20), nullable=False, server_default="neutral"),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("sym"),
    )

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    # Seed default PCR refresh interval = 30 minutes
    op.execute("INSERT INTO app_settings (key, value) VALUES ('pcr_refresh_interval_minutes', '30')")


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_table("volume_watchlist")
