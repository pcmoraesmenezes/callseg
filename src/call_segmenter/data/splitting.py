"""Divisão estável entre desenvolvimento e teste."""

import hashlib

TEST_FRACTION = 0.2


def assign_split(group_key: str, test_fraction: float = TEST_FRACTION) -> str:
    """Decide se um grupo de chamadas vai para `test` ou `development`.

    O destino sai do hash da chave, então uma chamada nunca troca de lado quando o conjunto cresce.
    A chave deve ser igual para textos idênticos (por exemplo, o hash do texto).
    """
    bucket = int(hashlib.sha256(group_key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "test" if bucket < test_fraction else "development"
