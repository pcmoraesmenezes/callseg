"""Treino do segmentador com as escolhas de produção."""

import pandas as pd

from call_segmenter import settings
from call_segmenter.models import CallSegmenter


def train_segmenter(
    calls: pd.DataFrame,
    estimator: str = settings.SECTOR_ESTIMATOR,
    regularization: float = settings.SECTOR_REGULARIZATION,
    low_confidence_threshold: float = settings.LOW_CONFIDENCE_THRESHOLD,
) -> CallSegmenter:
    """Treina um segmentador com os parâmetros de produção.

    Args:
        calls: tabela com `call_id`, `sector` e `transcript`.

    Returns:
        Segmentador ajustado, com `model_version` derivada dos dados e dos parâmetros.
    """
    segmenter = CallSegmenter(
        settings.CLUSTER_COUNTS,
        settings.load_subgroup_catalog(),
        settings.SEED,
        estimator=estimator,
        regularization=regularization,
        low_confidence_threshold=low_confidence_threshold,
    )
    return segmenter.fit(calls)
