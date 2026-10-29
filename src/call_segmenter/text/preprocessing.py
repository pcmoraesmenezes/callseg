"""Pré-processamento do texto antes de qualquer modelo."""

import re

PII_TAG = re.compile(r"\[([A-Z_]+)\]")


def mark_pii_tags(text: str) -> str:
    """Troca marcadores de dado pessoal por termos próprios.

    `[PERSON_NAME]` vira ` tagpersonname `. O marcador diz algo sobre a chamada
    (`tagmedicalcondition` aparece em consulta médica) e não pode se confundir com a palavra comum.
    """
    return PII_TAG.sub(lambda match: " tag" + match.group(1).lower().replace("_", "") + " ", text)


def count_words(text: str) -> int:
    """Número de palavras separadas por espaço."""
    return len(text.split())
