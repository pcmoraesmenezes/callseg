"""Ambiente do Alembic: usa a URL e o conjunto de tabelas do próprio pacote."""

from alembic import context
from sqlalchemy import create_engine, pool

from call_segmenter.warehouse.models import Base

config = context.config
target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    """Ignora tabelas de outros sistemas que dividem o servidor (Metabase e MLflow usam bancos próprios)."""
    return type_ != "table" or obj.schema in {"bronze", "silver", "gold", "ops"} or not reflected


def run_migrations_online() -> None:
    engine = create_engine(config.get_main_option("sqlalchemy.url").replace("%%", "%"), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_schemas=True, include_object=include_object
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
