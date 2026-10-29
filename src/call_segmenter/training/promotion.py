"""Decisão de promover um modelo candidato no lugar do vigente."""

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from call_segmenter import settings
from call_segmenter.models import CallSegmenter

from .evaluation import mcnemar_test, predict_sector_probabilities

SIGNIFICANCE_LEVEL = 0.05


@dataclass
class PromotionDecision:
    """Resultado da comparação entre o modelo vigente (champion) e o candidato (challenger)."""

    promote: bool
    reason: str
    champion_errors: int
    challenger_errors: int
    mcnemar_p_value: float
    challenger_latency_ms: float
    already_champion: bool = False


def measure_latency_ms(segmenter: CallSegmenter, transcripts: list[str], repeats: int = 50) -> float:
    """Mediana, em milissegundos, do tempo de segmentar uma chamada isolada."""
    samples = []
    for text in transcripts[:repeats]:
        started = time.perf_counter()
        segmenter.predict([text])
        samples.append((time.perf_counter() - started) * 1000)
    return float(np.median(samples))


def decide_promotion(
    champion: CallSegmenter | None,
    challenger: CallSegmenter,
    holdout: pd.DataFrame,
    latency_budget_ms: float = settings.LATENCY_BUDGET_MS,
) -> PromotionDecision:
    """Barra regressão: o candidato só entra se não for pior que o vigente nem estourar a latência.

    O candidato não precisa ser melhor, porque quase sempre foi treinado com mais dados e deve
    substituir o vigente quando empata. Ele é barrado se errar significativamente mais (McNemar,
    p < 0,05) ou se a latência mediana passar do orçamento.

    Também barra o candidato cujos grupos não casam com os nomes do catálogo, porque um retreino pode
    redesenhar os grupos e um nome errado numa tela é pior que nome nenhum.

    Args:
        champion: modelo vigente, ou None quando ainda não existe um.
        holdout: chamadas de teste que nenhum dos dois modelos viu no treino.
    """
    classes = challenger.sector_classifier.classes_
    truth = holdout.sector.to_numpy()
    challenger_prediction = classes[
        predict_sector_probabilities(challenger, holdout.transcript.tolist()).argmax(axis=1)
    ]
    challenger_errors = int((challenger_prediction != truth).sum())
    latency = measure_latency_ms(challenger, holdout.transcript.tolist())
    p_value, champion_errors, worse = 1.0, challenger_errors, False
    if champion is not None:
        champion_prediction = classes[
            predict_sector_probabilities(champion, holdout.transcript.tolist()).argmax(axis=1)
        ]
        comparison = mcnemar_test(truth, champion_prediction, challenger_prediction)
        p_value, champion_errors = comparison["p_value"], int((champion_prediction != truth).sum())
        worse = comparison["only_b_wrong"] > comparison["only_a_wrong"] and p_value < SIGNIFICANCE_LEVEL
    too_slow = latency > latency_budget_ms
    unnamed = challenger.naming_issues
    already_champion = champion is not None and champion.model_version == challenger.model_version
    if already_champion:
        reason = "o candidato é o mesmo modelo que já está vigente"
    elif unnamed:
        reason = f"os nomes dos subgrupos não descrevem os grupos novos e precisam de revisão: {unnamed}"
    elif worse:
        reason = "o candidato erra significativamente mais que o vigente"
    elif too_slow:
        reason = f"latência mediana do candidato ({latency:.1f} ms) acima do orçamento ({latency_budget_ms:.0f} ms)"
    elif champion is None:
        reason = "ainda não existe modelo vigente e o candidato cabe no orçamento de latência"
    else:
        reason = "o candidato não é pior que o vigente e cabe no orçamento de latência"
    return PromotionDecision(
        not (worse or too_slow or bool(unnamed) or already_champion),
        reason,
        champion_errors,
        challenger_errors,
        p_value,
        latency,
        already_champion,
    )
