"""Preparação do servidor Postgres e aplicação das migrações."""

from importlib import resources

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

EXTRA_DATABASES = ("metabase", "mlflow", "airflow")
BI_ROLE = "bi_reader"


def prepare_cluster(admin_url: str, bi_password: str, database: str) -> None:
    """Cria, se faltarem, os bancos do Metabase e do MLflow e o papel de leitura do BI.

    Roda com um usuário que tenha permissão de criar banco e papel. Pode ser executada quantas vezes se quiser.
    """
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        for name in EXTRA_DATABASES:
            if not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}):
                connection.execute(text(f'CREATE DATABASE "{name}"'))
        if not connection.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :name"), {"name": BI_ROLE}):
            connection.execute(text(f"CREATE ROLE {BI_ROLE} LOGIN"))
        connection.execute(
            text("SELECT set_config('callseg.bi_password', :password, false)"), {"password": bi_password}
        )
        connection.execute(
            text(
                f"DO $$ BEGIN EXECUTE format('ALTER ROLE {BI_ROLE} PASSWORD %L', "
                "current_setting('callseg.bi_password')); END $$"
            )
        )
        connection.execute(text(f'GRANT CONNECT ON DATABASE "{database}" TO {BI_ROLE}'))


def upgrade_schema(database_url: str, revision: str = "head") -> None:
    """Aplica as migrações até `revision`."""
    config = Config()
    config.set_main_option("script_location", str(resources.files("call_segmenter.warehouse").joinpath("migrations")))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, revision)
