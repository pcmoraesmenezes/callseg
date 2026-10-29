"""Ingestão em camadas: arquivos -> bronze (bruto) -> prata (limpo) -> ouro (versão do conjunto de dados).

Todos os passos são idempotentes: rodar de novo com os mesmos arquivos não muda nada, e arquivos novos
entram sem tocar nos que já estão lá. É isso que permite reexecutar o fluxo toda semana.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from call_segmenter.data import assign_split
from call_segmenter.data.transcripts import FILE_NAME_PATTERN, SECTORS

from .models import Call, DatasetVersion, QualityIssue, RawTranscript

CHUNK = 500


@dataclass
class IngestionSummary:
    """O que uma execução da ingestão fez."""

    batch_id: str
    files_seen: int
    files_new: int
    calls_added: int
    quality_issues: int
    dataset_version_id: int
    dataset_sha256: str


def load_bronze(session: Session, data_dir: Path, batch_id: str) -> tuple[int, int]:
    """Grava na camada bronze os arquivos que ainda não estão lá (comparados pelo hash do conteúdo).

    Returns:
        (arquivos vistos, arquivos novos).
    """
    known = set(session.execute(select(RawTranscript.source_path, RawTranscript.content_sha256)).all())
    seen = new = 0
    pending: list[dict] = []
    for sector in SECTORS:
        for path in sorted((Path(data_dir) / sector).glob("*.json")):
            seen += 1
            raw_bytes = path.read_bytes()
            digest = hashlib.sha256(raw_bytes).hexdigest()
            relative_path = f"{sector}/{path.name}"
            if (relative_path, digest) in known:
                continue
            known.add((relative_path, digest))
            payload = json.loads(raw_bytes) if raw_bytes.strip() else {}
            pending.append(
                {
                    "batch_id": batch_id,
                    "source_path": relative_path,
                    "sector_folder": sector,
                    "content_sha256": digest,
                    "payload": payload,
                }
            )
            new += 1
            if len(pending) >= CHUNK:
                session.execute(RawTranscript.__table__.insert(), pending)
                pending = []
    if pending:
        session.execute(RawTranscript.__table__.insert(), pending)
    session.commit()
    return seen, new


def build_silver(session: Session) -> tuple[int, int]:
    """Transforma em chamadas os arquivos bronze que ainda não foram processados.

    Registra em `silver.quality_issues` cada arquivo que não virou chamada: vazio, cópia de um id que já
    existe ou texto em branco. Arquivos originais são processados antes das cópias.

    Returns:
        (chamadas adicionadas, problemas de qualidade registrados).
    """
    processed = select(Call.bronze_id).union(select(QualityIssue.bronze_id))
    pending = session.scalars(select(RawTranscript).where(RawTranscript.id.not_in(processed))).all()
    existing_ids = set(session.scalars(select(Call.call_id)))
    ordered = sorted(pending, key=lambda row: not row.source_path.endswith("_transcript.json"))
    calls_added = issues = 0
    for raw in ordered:
        issue = _quality_issue(raw, existing_ids)
        if issue:
            session.add(QualityIssue(bronze_id=raw.id, issue=issue[0], detail=issue[1]))
            issues += 1
            continue
        call_id = FILE_NAME_PATTERN.match(Path(raw.source_path).name).group(1)
        transcript = raw.payload["text"]
        text_digest = hashlib.sha256(transcript.encode()).hexdigest()
        session.add(
            Call(
                call_id=call_id,
                sector=raw.sector_folder,
                transcript=transcript,
                asr_confidence=raw.payload.get("confidence"),
                duration_seconds=raw.payload.get("audio_duration"),
                word_count=len(raw.payload.get("words", [])),
                text_sha256=text_digest,
                split=assign_split(text_digest),
                bronze_id=raw.id,
            )
        )
        existing_ids.add(call_id)
        calls_added += 1
    session.commit()
    return calls_added, issues


def _quality_issue(raw: RawTranscript, existing_ids: set[str]) -> tuple[str, str | None] | None:
    if not raw.payload:
        return "arquivo_vazio", raw.source_path
    if not (raw.payload.get("text") or "").strip():
        return "texto_em_branco", raw.source_path
    call_id = FILE_NAME_PATTERN.match(Path(raw.source_path).name).group(1)
    if call_id in existing_ids:
        return "copia_de_id_existente", f"{raw.source_path} repete o id {call_id}"
    return None


def register_dataset_version(session: Session) -> DatasetVersion:
    """Registra (ou reencontra) a versão do conjunto de dados formada pelas chamadas atuais da prata."""
    rows = session.execute(select(Call.call_id, Call.text_sha256, Call.sector).order_by(Call.call_id)).all()
    digest = hashlib.sha256("\n".join(f"{call_id}:{text}" for call_id, text, _ in rows).encode()).hexdigest()
    version = session.scalar(select(DatasetVersion).where(DatasetVersion.data_sha256 == digest))
    if version is None:
        per_sector = pd.Series([sector for _, _, sector in rows]).value_counts().to_dict()
        version = DatasetVersion(
            data_sha256=digest, calls=len(rows), per_sector={k: int(v) for k, v in per_sector.items()}
        )
        session.add(version)
        session.commit()
    return version


def ingest_directory(session: Session, data_dir: str | Path) -> IngestionSummary:
    """Executa as três etapas sobre `data_dir/<setor>/*.json`."""
    batch_id = uuid.uuid4().hex[:12]
    seen, new = load_bronze(session, Path(data_dir), batch_id)
    calls_added, issues = build_silver(session)
    version = register_dataset_version(session)
    return IngestionSummary(batch_id, seen, new, calls_added, issues, version.id, version.data_sha256)


def load_calls(session: Session, split: str | None = None) -> pd.DataFrame:
    """Lê as chamadas da camada prata.

    Args:
        split: `development`, `test` ou None para todas.

    Returns:
        Tabela com call_id, sector, transcript, asr_confidence, duration_seconds, word_count, text_sha256, split.
    """
    query = select(
        Call.call_id,
        Call.sector,
        Call.transcript,
        Call.asr_confidence,
        Call.duration_seconds,
        Call.word_count,
        Call.text_sha256,
        Call.split,
    ).order_by(Call.call_id)
    if split:
        query = query.where(Call.split == split)
    return pd.DataFrame(
        session.execute(query).all(),
        columns=[
            "call_id",
            "sector",
            "transcript",
            "asr_confidence",
            "duration_seconds",
            "word_count",
            "text_sha256",
            "split",
        ],
    )


def count_calls(session: Session) -> int:
    """Número de chamadas na prata."""
    return int(session.scalar(select(func.count()).select_from(Call)))
