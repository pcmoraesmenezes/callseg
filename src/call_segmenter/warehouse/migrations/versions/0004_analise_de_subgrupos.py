"""Medidas das análises de subgrupos para o painel de modelos.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subgroup_analysis",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("analysis", sa.Text(), nullable=False),
        sa.Column("sector", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="gold",
    )
    op.execute("GRANT SELECT ON gold.subgroup_analysis TO bi_reader") if _reader_exists() else None


def _reader_exists() -> bool:
    return bool(op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bi_reader')")))


def downgrade() -> None:
    op.drop_table("subgroup_analysis", schema="gold")
