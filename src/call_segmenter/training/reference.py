"""Referência de deriva: como o modelo se comporta em chamadas que ele não viu no treino."""

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict

from call_segmenter.models import CallSegmenter
from call_segmenter.models.sector_classifier import build_sector_pipeline
from call_segmenter.models.subgroup_clusterer import AMBIGUOUS_QUANTILE
from call_segmenter.monitoring import DriftBaseline

FOLDS = 5


def compute_drift_baseline(calls: pd.DataFrame, segmenter: CallSegmenter, seed: int = 0) -> DriftBaseline:
    """Mede, por validação cruzada agrupada por texto, a confiança do setor nas chamadas de treino.

    A taxa de atribuição frágil é fixada pelo quantil usado no treino dos subgrupos.
    """
    pipeline = build_sector_pipeline(
        segmenter.estimator, segmenter.regularization, segmenter.tfidf_overrides, **segmenter.estimator_params
    )
    folds = StratifiedGroupKFold(FOLDS, shuffle=True, random_state=seed)
    groups = calls.text_sha256 if "text_sha256" in calls else calls.call_id
    probabilities = cross_val_predict(
        pipeline, calls.transcript, calls.sector, groups=groups, cv=folds, method="predict_proba"
    )
    best = probabilities.max(axis=1)
    return DriftBaseline(
        low_confidence_rate=float(np.mean(best < segmenter.low_confidence_threshold)),
        ambiguous_rate=AMBIGUOUS_QUANTILE,
        mean_probability=float(best.mean()),
        sector_mix=calls.sector.value_counts(normalize=True).to_dict(),
    )
