"""Conexão com o banco."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import SCHEMAS

SQLITE_SCHEMA_MAP = {schema: None for schema in SCHEMAS}


def create_db_engine(url: str) -> Engine:
    """Cria o engine. Em SQLite (testes) os schemas das camadas são ignorados, porque o SQLite não os tem."""
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        engine = engine.execution_options(schema_translate_map=SQLITE_SCHEMA_MAP)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Fábrica de sessões; cada uso abre e fecha uma transação."""
    return sessionmaker(engine, expire_on_commit=False)
