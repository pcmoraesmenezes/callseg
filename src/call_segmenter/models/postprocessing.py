"""Pós-processamento: transforma as saídas cruas dos modelos em sinais que o consumidor da API entende."""

SHORT_CALL_WORDS = 100


def is_low_confidence(sector_probability: float, threshold: float) -> bool:
    """True quando a maior probabilidade de setor fica abaixo do limiar de confiança."""
    return sector_probability < threshold


def call_warnings(word_count: int) -> list[str]:
    """Avisos sobre a entrada. `transcricao_curta` quando há menos de `SHORT_CALL_WORDS` palavras."""
    return ["transcricao_curta"] if word_count < SHORT_CALL_WORDS else []
