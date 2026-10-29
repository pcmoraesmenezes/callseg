"""Sinais de deriva: compara a janela recente de predições com uma referência fora da amostra."""

import math
from dataclasses import dataclass, field

MIN_CALLS = 30
Z_LIMIT = 3.0
PSI_LIMIT = 0.2
PROBABILITY_DROP_POINTS = 5.0


@dataclass
class DriftBaseline:
    """Referência medida em validação cruzada.

    `sector_mix` é a participação de cada setor (soma 1); as taxas e a probabilidade média estão em 0..1.
    """

    low_confidence_rate: float
    ambiguous_rate: float
    mean_probability: float
    sector_mix: dict[str, float]


@dataclass
class DriftWindow:
    """Predições recentes: contagem, taxas, probabilidade média (0..1) e mistura de setores."""

    calls: int
    low_confidence_rate: float
    ambiguous_rate: float
    mean_probability: float
    sector_mix: dict[str, float]


@dataclass
class DriftReport:
    """Resultado de uma checagem: status, alertas e as medidas que os sustentam."""

    status: str
    calls: int
    alerts: list[str] = field(default_factory=list)
    measures: dict[str, float] = field(default_factory=dict)


def population_stability_index(baseline: dict[str, float], window: dict[str, float]) -> float:
    """PSI entre duas distribuições discretas. Acima de 0,2 a mistura mudou de forma relevante."""
    total = 0.0
    for key in set(baseline) | set(window):
        expected, observed = max(baseline.get(key, 0.0), 1e-4), max(window.get(key, 0.0), 1e-4)
        total += (observed - expected) * math.log(observed / expected)
    return total


def z_score(observed: float, expected: float, sample_size: int) -> float:
    """Quantos desvios padrão a taxa observada está acima da esperada (aproximação binomial)."""
    return (observed - expected) / math.sqrt(expected * (1 - expected) / sample_size)


def evaluate_window(baseline: DriftBaseline, window: DriftWindow) -> DriftReport:
    """Aponta alertas quando a janela se afasta da referência.

    Alerta quando a taxa de baixa confiança ou de atribuição frágil sobe mais de `Z_LIMIT` desvios,
    quando a mistura de setores tem PSI acima de `PSI_LIMIT` ou quando a probabilidade média cai
    mais de `PROBABILITY_DROP_POINTS` pontos percentuais. Janela com menos de `MIN_CALLS` não decide.
    """
    if window.calls < MIN_CALLS:
        return DriftReport("amostra pequena demais para decidir", window.calls)
    z_low = z_score(window.low_confidence_rate, baseline.low_confidence_rate, window.calls)
    z_ambiguous = z_score(window.ambiguous_rate, baseline.ambiguous_rate, window.calls)
    psi = population_stability_index(baseline.sector_mix, window.sector_mix)
    alerts = []
    if z_low > Z_LIMIT:
        alerts.append(
            f"chamadas com baixa confiança subiram de {baseline.low_confidence_rate:.1%} "
            f"para {window.low_confidence_rate:.1%}"
        )
    if z_ambiguous > Z_LIMIT:
        alerts.append(
            f"taxa de atribuição frágil subiu de {baseline.ambiguous_rate:.1%} para {window.ambiguous_rate:.1%}"
        )
    if psi > PSI_LIMIT:
        alerts.append(f"mistura de setores mudou (PSI {psi:.2f})")
    if (baseline.mean_probability - window.mean_probability) * 100 > PROBABILITY_DROP_POINTS:
        alerts.append(
            f"confiança média do setor caiu de {baseline.mean_probability:.1%} para {window.mean_probability:.1%}"
        )
    measures = {
        "z_low_confidence": round(z_low, 2),
        "z_ambiguous": round(z_ambiguous, 2),
        "sector_psi": round(psi, 3),
        "low_confidence_rate": round(window.low_confidence_rate, 3),
        "ambiguous_rate": round(window.ambiguous_rate, 3),
        "mean_probability": round(window.mean_probability, 4),
    }
    return DriftReport("alerta" if alerts else "ok", window.calls, alerts, measures)
