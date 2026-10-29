"""Visões para o BI e permissão de leitura só sobre agregados.

O papel `bi_reader` lê as visões e as tabelas de ouro e de operação. Não lê a camada bronze nem a prata,
que guardam o texto das chamadas.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

VIEWS = {
    "v_subgroup_mix": """
        SELECT source, sector, subgroup_name, count(*) AS calls,
               round(avg(ambiguous::int)::numeric, 3) AS ambiguous_rate,
               round(avg(sector_probability)::numeric, 3) AS mean_sector_probability
        FROM ops.predictions GROUP BY source, sector, subgroup_name""",
    "v_daily": """
        SELECT date_trunc('day', ts) AS day, source, sector, count(*) AS calls,
               round(avg(ambiguous::int)::numeric, 3) AS ambiguous_rate,
               round(avg(low_confidence::int)::numeric, 3) AS low_confidence_rate,
               round(avg(sector_probability)::numeric, 3) AS mean_sector_probability,
               round(avg(latency_ms)::numeric, 2) AS mean_latency_ms
        FROM ops.predictions GROUP BY 1, 2, 3""",
    "v_minutely": """
        SELECT date_trunc('minute', ts) AS minute, sector, count(*) AS calls,
               round(avg(ambiguous::int)::numeric * 100, 1) AS ambiguous_pct,
               round(avg(sector_probability)::numeric * 100, 1) AS sector_probability_pct,
               round(avg(low_confidence::int)::numeric * 100, 1) AS low_confidence_pct
        FROM ops.predictions WHERE source = 'api' GROUP BY 1, 2""",
    "v_shadow_agreement": """
        SELECT date_trunc('hour', ts) AS hour, shadow_version, count(*) AS calls,
               round(avg((champion_sector = shadow_sector)::int)::numeric, 4) AS sector_agreement,
               round(avg((champion_subgroup = shadow_subgroup)::int)::numeric, 4) AS subgroup_agreement,
               round(avg(shadow_latency_ms)::numeric, 2) AS mean_shadow_latency_ms
        FROM ops.shadow_predictions GROUP BY 1, 2""",
}


def upgrade() -> None:
    for name, query in VIEWS.items():
        op.execute(f"CREATE OR REPLACE VIEW gold.{name} AS {query}")
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'bi_reader') THEN
            GRANT USAGE ON SCHEMA gold, ops TO bi_reader;
            GRANT SELECT ON ALL TABLES IN SCHEMA gold TO bi_reader;
            GRANT SELECT ON ops.predictions, ops.model_benchmark, ops.drift_checks TO bi_reader;
            ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO bi_reader;
          END IF;
        END $$""")


def downgrade() -> None:
    for name in VIEWS:
        op.execute(f"DROP VIEW IF EXISTS gold.{name}")
