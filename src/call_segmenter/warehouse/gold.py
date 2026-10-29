"""Camada ouro: agregados prontos para o BI. Nunca contém texto de chamada."""

import numpy as np
import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .ingestion import load_calls
from .models import HoldoutConfusion, SectorProfile, SizeHistogram

WORDS_BIN_WIDTH = 100
WORDS_CAP = 3000
CONFIDENCE_BIN_WIDTH = 0.01


def build_sector_aggregates(session: Session) -> int:
    """Recalcula o perfil e os histogramas de cada setor a partir da prata.

    Returns:
        Número de setores resumidos.
    """
    calls = load_calls(session)
    session.execute(delete(SectorProfile))
    session.execute(delete(SizeHistogram))
    for sector, group in calls.groupby("sector"):
        words = group.word_count
        session.add(
            SectorProfile(
                sector=sector,
                calls=len(group),
                words_p05=float(words.quantile(0.05)),
                words_p50=float(words.median()),
                words_p95=float(words.quantile(0.95)),
                duration_p50=float(group.duration_seconds.median()),
                confidence_p50=float(group.asr_confidence.median()),
            )
        )
        session.add_all(_histogram(sector, "words", words.clip(upper=WORDS_CAP), WORDS_BIN_WIDTH))
        session.add_all(_histogram(sector, "asr_confidence", group.asr_confidence, CONFIDENCE_BIN_WIDTH))
    session.commit()
    return calls.sector.nunique()


def _histogram(sector: str, measure: str, values: pd.Series, bin_width: float) -> list[SizeHistogram]:
    starts = (np.floor(values.dropna() / bin_width) * bin_width).round(4)
    return [
        SizeHistogram(sector=sector, measure=measure, bin_start=float(start), calls=int(count))
        for start, count in starts.value_counts().items()
    ]


def record_holdout_confusion(session: Session, model_version: str, truth: pd.Series, predicted: pd.Series) -> None:
    """Grava a matriz de confusão do modelo no teste, substituindo a anterior da mesma versão."""
    session.execute(delete(HoldoutConfusion).where(HoldoutConfusion.model_version == model_version))
    counts = pd.crosstab(truth.to_numpy(), predicted.to_numpy()).stack()
    session.add_all(
        [
            HoldoutConfusion(model_version=model_version, true_sector=true, predicted_sector=guess, calls=int(calls))
            for (true, guess), calls in counts.items()
        ]
    )
    session.commit()
