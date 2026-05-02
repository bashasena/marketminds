"""option_oi_ticks for ATM-band rolling PCR

Revision ID: 20260428_0003
Revises: 20260425_0002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260428_0003"
down_revision: Union[str, None] = "20260425_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "option_oi_ticks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("expiry", sa.String(length=64), nullable=True),
        sa.Column("spot", sa.Float(), nullable=True),
        sa.Column("atm_call_oi", sa.Float(), nullable=False),
        sa.Column("atm_put_oi", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_option_oi_ticks_captured_at"), "option_oi_ticks", ["captured_at"], unique=False)
    op.create_index(op.f("ix_option_oi_ticks_market_id"), "option_oi_ticks", ["market_id"], unique=False)
    op.create_index(op.f("ix_option_oi_ticks_symbol"), "option_oi_ticks", ["symbol"], unique=False)
    op.create_index(
        "ix_option_oi_ticks_market_symbol_cap",
        "option_oi_ticks",
        ["market_id", "symbol", "captured_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_option_oi_ticks_market_symbol_cap", table_name="option_oi_ticks")
    op.drop_index(op.f("ix_option_oi_ticks_symbol"), table_name="option_oi_ticks")
    op.drop_index(op.f("ix_option_oi_ticks_market_id"), table_name="option_oi_ticks")
    op.drop_index(op.f("ix_option_oi_ticks_captured_at"), table_name="option_oi_ticks")
    op.drop_table("option_oi_ticks")
