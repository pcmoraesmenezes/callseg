"""Arquivos do modelo: o binário e os metadados que o acompanham."""

import json
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from call_segmenter.models import CallSegmenter
from call_segmenter.monitoring import DriftBaseline


def metadata_path(model_path: str | Path) -> Path:
    """Caminho do JSON de metadados que fica ao lado do modelo (`x.joblib` -> `x.meta.json`)."""
    return Path(model_path).with_suffix(".meta.json")


def save_model(segmenter: CallSegmenter, model_path: str | Path, metadata: dict) -> None:
    """Grava o modelo e seus metadados (versão, data, dados de treino, medidas, referência de deriva)."""
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    segmenter.save(str(model_path))
    document = {
        "model_version": segmenter.model_version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_train": segmenter.n_train,
        "estimator": segmenter.estimator,
        **metadata,
    }
    metadata_path(model_path).write_text(json.dumps(document, ensure_ascii=False, indent=1, default=str))


def read_metadata(model_path: str | Path) -> dict:
    """Lê os metadados gravados por `save_model`."""
    return json.loads(metadata_path(model_path).read_text())


def baseline_of(model_path: str | Path) -> DriftBaseline:
    """Referência de deriva gravada junto do modelo."""
    return DriftBaseline(**read_metadata(model_path)["drift_baseline"])


def archive_and_replace(challenger_path: str | Path, champion_path: str | Path, archive_dir: str | Path) -> None:
    """Guarda o vigente em `archive_dir/<versão>.joblib` e coloca o candidato no lugar dele."""
    champion_path = Path(champion_path)
    if champion_path.exists():
        archive = Path(archive_dir)
        archive.mkdir(parents=True, exist_ok=True)
        version = read_metadata(champion_path)["model_version"]
        shutil.copy2(champion_path, archive / f"{version}.joblib")
        shutil.copy2(metadata_path(champion_path), archive / f"{version}.meta.json")
    shutil.copy2(challenger_path, champion_path)
    shutil.copy2(metadata_path(challenger_path), metadata_path(champion_path))


def baseline_as_dict(baseline: DriftBaseline) -> dict:
    return asdict(baseline)
