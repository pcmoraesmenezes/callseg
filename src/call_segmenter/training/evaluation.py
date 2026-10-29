"""Avaliação de um segmentador em chamadas que ele não viu."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy.stats import binomtest
from sklearn.metrics import accuracy_score, f1_score, log_loss

from call_segmenter.models import CallSegmenter


@dataclass
class HoldoutReport:
    """Medidas de um segmentador no conjunto de teste."""

    f1_macro: float
    accuracy: float
    errors: int
    calls: int
    expected_calibration_error: float
    log_loss: float

    def to_dict(self) -> dict:
        return asdict(self)


def expected_calibration_error(probabilities: np.ndarray, correct: np.ndarray, bins: int = 10) -> float:
    """Média, ponderada pelo tamanho de cada faixa, da distância entre a confiança e o acerto real."""
    confidence = probabilities.max(axis=1)
    bin_of = np.clip((confidence * bins).astype(int), 0, bins - 1)
    return float(
        sum(
            (bin_of == b).mean() * abs(confidence[bin_of == b].mean() - correct[bin_of == b].mean())
            for b in range(bins)
            if (bin_of == b).any()
        )
    )


def predict_sector_probabilities(segmenter: CallSegmenter, transcripts: list[str]) -> np.ndarray:
    """Probabilidade de cada setor por chamada, na ordem de `segmenter.sector_classifier.classes_`."""
    return segmenter.sector_classifier.predict_proba(transcripts)


def evaluate_on_holdout(segmenter: CallSegmenter, holdout: pd.DataFrame) -> HoldoutReport:
    """Mede o classificador de setor em chamadas de teste.

    Args:
        holdout: tabela com `sector` e `transcript`.
    """
    probabilities = predict_sector_probabilities(segmenter, holdout.transcript.tolist())
    classes = segmenter.sector_classifier.classes_
    predicted = classes[probabilities.argmax(axis=1)]
    truth = holdout.sector.to_numpy()
    return HoldoutReport(
        f1_macro=float(f1_score(truth, predicted, average="macro")),
        accuracy=float(accuracy_score(truth, predicted)),
        errors=int((predicted != truth).sum()),
        calls=len(holdout),
        expected_calibration_error=expected_calibration_error(probabilities, predicted == truth),
        log_loss=float(log_loss(truth, probabilities, labels=list(classes))),
    )


def mcnemar_test(truth: np.ndarray, prediction_a: np.ndarray, prediction_b: np.ndarray) -> dict:
    """Compara dois modelos nas chamadas em que eles discordam.

    Returns:
        `only_a_wrong`, `only_b_wrong` e o valor p exato (binomial, bicaudal).
    """
    only_a_wrong = int(((prediction_a != truth) & (prediction_b == truth)).sum())
    only_b_wrong = int(((prediction_b != truth) & (prediction_a == truth)).sum())
    discordant = only_a_wrong + only_b_wrong
    p_value = float(binomtest(min(only_a_wrong, only_b_wrong), discordant, 0.5).pvalue) if discordant else 1.0
    return {"only_a_wrong": only_a_wrong, "only_b_wrong": only_b_wrong, "p_value": p_value}
