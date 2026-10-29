"""Impressão digital do conjunto de dados: identifica a versão dos dados que treinou um modelo."""

import hashlib
from pathlib import Path


def dataset_fingerprint(data_dir: str | Path) -> dict:
    """Calcula o hash de cada setor e o hash geral, sem copiar nenhum conteúdo.

    Returns:
        Dicionário com `sha256` geral e, por setor, o número de arquivos e o `sha256`.
    """
    root = Path(data_dir)
    per_sector, overall = {}, hashlib.sha256()
    for sector in sorted(path.name for path in root.iterdir() if path.is_dir()):
        files = sorted((root / sector).glob("*.json"))
        sector_digest = hashlib.sha256()
        for file in files:
            sector_digest.update(file.name.encode() + hashlib.sha256(file.read_bytes()).digest())
        per_sector[sector] = {"files": len(files), "sha256": sector_digest.hexdigest()}
        overall.update(sector_digest.digest())
    return {"sha256": overall.hexdigest(), "sectors": per_sector}
