"""Leitura dos arquivos de transcrição e remoção de chamadas repetidas."""

import json
import re
from pathlib import Path

import pandas as pd

SECTORS: tuple[str, ...] = ("automotive", "home_service", "medicare")
FILE_NAME_PATTERN = re.compile(r"([0-9a-f]+)(.*)\.json$")


def parse_transcript_file(path: Path, sector: str) -> dict | None:
    """Lê um arquivo de transcrição.

    Args:
        path: caminho do JSON da chamada.
        sector: setor a que a pasta do arquivo pertence.

    Returns:
        Um registro com os campos da chamada, ou None se o arquivo estiver vazio.
    """
    raw_bytes = path.read_bytes()
    if not raw_bytes.strip():
        return None
    document = json.loads(raw_bytes)
    call_id = FILE_NAME_PATTERN.match(path.name).group(1)
    return {
        "sector": sector,
        "file_name": path.name,
        "call_id": call_id,
        "is_extra_copy": path.name != f"{call_id}_transcript.json",
        "transcript": document.get("text") or "",
        "asr_confidence": document.get("confidence"),
        "duration_seconds": document.get("audio_duration"),
        "word_count": len(document.get("words", [])),
    }


def read_transcripts(data_dir: str | Path, sectors: tuple[str, ...] = SECTORS) -> pd.DataFrame:
    """Lê todos os arquivos de `data_dir/<setor>/*.json`.

    Returns:
        Tabela com uma linha por arquivo não vazio. Colunas: sector, file_name, call_id,
        is_extra_copy, transcript, asr_confidence, duration_seconds, word_count.
    """
    records = []
    for sector in sectors:
        for path in sorted((Path(data_dir) / sector).glob("*.json")):
            record = parse_transcript_file(path, sector)
            if record is not None:
                records.append(record)
    return pd.DataFrame(records)


def deduplicate_calls(files: pd.DataFrame) -> pd.DataFrame:
    """Mantém uma linha por chamada, preferindo o arquivo original à cópia (`... 2.json`, `... (1).json`).

    Args:
        files: tabela devolvida por `read_transcripts`.

    Returns:
        Tabela sem transcrições em branco e com `call_id` único.
    """
    with_text = files[files.transcript.str.strip() != ""]
    ordered = with_text.sort_values(["call_id", "is_extra_copy"])
    return ordered.drop_duplicates("call_id").reset_index(drop=True)
