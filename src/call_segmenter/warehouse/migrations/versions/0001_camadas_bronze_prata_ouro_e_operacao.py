"""Camadas bronze, prata, ouro e operação.

Se o banco vem da versão anterior (tabelas soltas em `public`), a tabela de predições é movida
para `ops` com seus dados; o resto da versão anterior (visões e a tabela de comparação de
modelos) é recriado em seguida.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    for schema in ("bronze", "silver", "gold", "ops"):
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    for legacy in ("v_subgroup_mix", "v_daily", "v_minutely"):
        op.execute(f"DROP VIEW IF EXISTS public.{legacy}")
    op.execute("DROP TABLE IF EXISTS public.model_benchmark")
    legacy_predictions = op.get_bind().scalar(sa.text("SELECT to_regclass('public.predictions') IS NOT NULL"))
    if legacy_predictions:
        op.execute("ALTER TABLE public.predictions SET SCHEMA ops")
    op.create_table(
        "raw_transcripts",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("sector_folder", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column(
            "payload", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_path", "content_sha256", name="raw_transcripts_file_version"),
        schema="bronze",
    )
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data_sha256", sa.Text(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.Column(
            "per_sector", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("data_sha256"),
        schema="gold",
    )
    op.create_table(
        "drift_checks",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("window_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.Column(
            "alerts", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column(
            "measures", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="ops",
    )
    op.create_table(
        "model_benchmark",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("representation", sa.Text(), nullable=True),
        sa.Column("trial", sa.Integer(), nullable=True),
        sa.Column("f1_macro", sa.Float(), nullable=True),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("fit_seconds", sa.Float(), nullable=True),
        sa.Column("errors", sa.Integer(), nullable=True),
        sa.Column("ece", sa.Float(), nullable=True),
        sa.Column(
            "parameters", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="ops",
    )
    op.create_index("model_benchmark_stage_idx", "model_benchmark", ["stage", "f1_macro"], unique=False, schema="ops")
    if not legacy_predictions:
        op.create_table(
            "predictions",
            sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
            sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("request_id", sa.Text(), nullable=False),
            sa.Column("source", sa.Text(), nullable=False),
            sa.Column("model_version", sa.Text(), nullable=False),
            sa.Column("sector", sa.Text(), nullable=False),
            sa.Column("sector_probability", sa.Float(), nullable=False),
            sa.Column("low_confidence", sa.Boolean(), nullable=False),
            sa.Column("subgroup_id", sa.Integer(), nullable=False),
            sa.Column("subgroup_name", sa.Text(), nullable=False),
            sa.Column("margin", sa.Float(), nullable=False),
            sa.Column("ambiguous", sa.Boolean(), nullable=False),
            sa.Column("n_words", sa.Integer(), nullable=False),
            sa.Column("latency_ms", sa.Float(), nullable=False),
            sa.Column("text_sha256", sa.Text(), nullable=False),
            sa.CheckConstraint("source IN ('api', 'dataset')", name="prediction_source_valid"),
            sa.PrimaryKeyConstraint("id"),
            schema="ops",
        )
        op.create_index(
            "predictions_source_sector_idx", "predictions", ["source", "sector"], unique=False, schema="ops"
        )
        op.create_index("predictions_ts_idx", "predictions", ["ts"], unique=False, schema="ops")
    op.create_table(
        "shadow_predictions",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("champion_version", sa.Text(), nullable=False),
        sa.Column("shadow_version", sa.Text(), nullable=False),
        sa.Column("champion_sector", sa.Text(), nullable=False),
        sa.Column("shadow_sector", sa.Text(), nullable=False),
        sa.Column("champion_subgroup", sa.Text(), nullable=False),
        sa.Column("shadow_subgroup", sa.Text(), nullable=False),
        sa.Column("shadow_latency_ms", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="ops",
    )
    op.create_index("shadow_predictions_ts_idx", "shadow_predictions", ["ts"], unique=False, schema="ops")
    op.create_table(
        "model_versions",
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("dataset_version_id", sa.Integer(), nullable=True),
        sa.Column("estimator", sa.Text(), nullable=False),
        sa.Column(
            "parameters", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column(
            "metrics", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('challenger', 'champion', 'retired', 'rejected')", name="model_status_valid"),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["gold.dataset_versions.id"],
        ),
        sa.PrimaryKeyConstraint("model_version"),
        schema="gold",
    )
    op.create_table(
        "calls",
        sa.Column("call_id", sa.Text(), nullable=False),
        sa.Column("sector", sa.Text(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("asr_confidence", sa.Float(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("text_sha256", sa.Text(), nullable=False),
        sa.Column("split", sa.Text(), nullable=False),
        sa.Column("bronze_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("split IN ('development', 'test')", name="calls_split_valid"),
        sa.ForeignKeyConstraint(
            ["bronze_id"],
            ["bronze.raw_transcripts.id"],
        ),
        sa.PrimaryKeyConstraint("call_id"),
        schema="silver",
    )
    op.create_index("calls_sector_split_idx", "calls", ["sector", "split"], unique=False, schema="silver")
    op.create_table(
        "quality_issues",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("bronze_id", sa.BigInteger(), nullable=False),
        sa.Column("issue", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("found_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["bronze_id"],
            ["bronze.raw_transcripts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="silver",
    )


def downgrade() -> None:
    op.drop_table("quality_issues", schema="silver")
    op.drop_index("calls_sector_split_idx", table_name="calls", schema="silver")
    op.drop_table("calls", schema="silver")
    op.drop_table("model_versions", schema="gold")
    op.drop_index("shadow_predictions_ts_idx", table_name="shadow_predictions", schema="ops")
    op.drop_table("shadow_predictions", schema="ops")
    op.drop_index("predictions_ts_idx", table_name="predictions", schema="ops")
    op.drop_index("predictions_source_sector_idx", table_name="predictions", schema="ops")
    op.drop_table("predictions", schema="ops")
    op.drop_index("model_benchmark_stage_idx", table_name="model_benchmark", schema="ops")
    op.drop_table("model_benchmark", schema="ops")
    op.drop_table("drift_checks", schema="ops")
    op.drop_table("dataset_versions", schema="gold")
    op.drop_table("raw_transcripts", schema="bronze")
