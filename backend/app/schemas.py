"""Formato das requisições e das respostas da API."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import Settings

SETTINGS = Settings()


class Call(BaseModel):
    """Uma chamada. Só `text` é lido, então o JSON do conjunto de dados pode ser enviado inteiro."""

    model_config = ConfigDict(extra="ignore")
    text: str = Field(
        max_length=SETTINGS.max_transcript_chars,
        description="Transcrição completa. Aceita o JSON do dataset inteiro; só `text` é lido.",
    )

    @field_validator("text")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a transcrição está vazia")
        return value


class Batch(BaseModel):
    """Até `max_batch` chamadas, devolvidas na mesma ordem."""

    calls: list[Call] = Field(min_length=1, max_length=SETTINGS.max_batch)


class Subgroup(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    similarity: float = Field(description="Similaridade de cosseno com o centro do subgrupo.")
    margin: float = Field(description="Diferença para o segundo subgrupo mais próximo.")
    ambiguous: bool = Field(description="Margem entre as 10% menores do treino: a atribuição é frágil.")
    runner_up: str


class Evidence(BaseModel):
    sector_terms: list[str] = Field(description="Termos da chamada que mais pesaram para o setor.")
    subgroup_terms: list[str] = Field(description="Termos da chamada que definem o subgrupo atribuído.")


class Segmentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    request_id: str
    model_version: str
    sector: str
    sector_probability: float
    sector_scores: dict[str, float]
    low_confidence: bool = Field(description="Probabilidade do setor abaixo do limiar (ver /health).")
    subgroup: Subgroup
    evidence: Evidence | None = Field(None, description="Presente só com `explain=true`.")
    warnings: list[str]
    latency_ms: float
