"""Configuração lida do ambiente."""

import os
from dataclasses import dataclass, field
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Parâmetros da API. Todos vêm de variáveis de ambiente, com padrão para desenvolvimento local."""

    model_path: str = field(default_factory=lambda: os.environ.get("MODEL_PATH", "models/segmenter.joblib"))
    shadow_model_path: str | None = field(default_factory=lambda: os.environ.get("SHADOW_MODEL_PATH") or None)
    database_url: str | None = field(default_factory=lambda: os.environ.get("DATABASE_URL"))
    frontend_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("FRONTEND_DIR", REPOSITORY_ROOT / "frontend"))
    )
    max_batch: int = 50
    max_transcript_chars: int = 200_000
