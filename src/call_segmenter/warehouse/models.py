"""Tabelas do banco, em camadas: bronze (bruto), prata (limpo), ouro (pronto para uso) e operação (API)."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Json = JSON().with_variant(JSONB(), "postgresql")
BigId = BigInteger().with_variant(Integer(), "sqlite")
SCHEMAS = ("bronze", "silver", "gold", "ops")


class Base(DeclarativeBase):
    """Base das tabelas. Cada tabela declara o schema da sua camada."""


class RawTranscript(Base):
    """Bronze: o arquivo como chegou, sem alteração. Só recebe linhas novas (caminho + hash do conteúdo)."""

    __tablename__ = "raw_transcripts"
    __table_args__ = (
        UniqueConstraint("source_path", "content_sha256", name="raw_transcripts_file_version"),
        {"schema": "bronze"},
    )

    id: Mapped[int] = mapped_column(BigId, primary_key=True)
    batch_id: Mapped[str] = mapped_column(Text)
    source_path: Mapped[str] = mapped_column(Text)
    sector_folder: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(Json)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Call(Base):
    """Prata: uma linha por chamada, tipada, sem cópias, com a divisão desenvolvimento/teste já decidida."""

    __tablename__ = "calls"
    __table_args__ = (
        CheckConstraint("split IN ('development', 'test')", name="calls_split_valid"),
        Index("calls_sector_split_idx", "sector", "split"),
        {"schema": "silver"},
    )

    call_id: Mapped[str] = mapped_column(Text, primary_key=True)
    sector: Mapped[str] = mapped_column(Text)
    transcript: Mapped[str] = mapped_column(Text)
    asr_confidence: Mapped[float | None] = mapped_column(Float)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    word_count: Mapped[int] = mapped_column(Integer)
    text_sha256: Mapped[str] = mapped_column(Text)
    split: Mapped[str] = mapped_column(Text)
    bronze_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("bronze.raw_transcripts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QualityIssue(Base):
    """Prata: arquivo da camada bronze que não virou chamada, e por quê (vazio, cópia, texto em branco)."""

    __tablename__ = "quality_issues"
    __table_args__ = {"schema": "silver"}

    id: Mapped[int] = mapped_column(BigId, primary_key=True)
    bronze_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("bronze.raw_transcripts.id"))
    issue: Mapped[str] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)
    found_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DatasetVersion(Base):
    """Ouro: a versão do conjunto de dados, identificada pelo hash das chamadas que a compõem."""

    __tablename__ = "dataset_versions"
    __table_args__ = {"schema": "gold"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_sha256: Mapped[str] = mapped_column(Text, unique=True)
    calls: Mapped[int] = mapped_column(Integer)
    per_sector: Mapped[dict] = mapped_column(Json)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelVersion(Base):
    """Ouro: cada modelo treinado, com a versão dos dados, as medidas e o estado (candidato, vigente ou aposentado)."""

    __tablename__ = "model_versions"
    __table_args__ = (
        CheckConstraint("status IN ('challenger', 'champion', 'retired', 'rejected')", name="model_status_valid"),
        {"schema": "gold"},
    )

    model_version: Mapped[str] = mapped_column(Text, primary_key=True)
    dataset_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gold.dataset_versions.id"))
    estimator: Mapped[str] = mapped_column(Text)
    parameters: Mapped[dict] = mapped_column(Json)
    metrics: Mapped[dict] = mapped_column(Json)
    status: Mapped[str] = mapped_column(Text)
    status_reason: Mapped[str | None] = mapped_column(Text)
    artifact_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Prediction(Base):
    """Operação: cada segmentação feita pela API ou pontuada em lote. Nunca guarda o texto, só o hash."""

    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("source IN ('api', 'dataset')", name="prediction_source_valid"),
        Index("predictions_ts_idx", "ts"),
        Index("predictions_source_sector_idx", "source", "sector"),
        {"schema": "ops"},
    )

    id: Mapped[int] = mapped_column(BigId, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    request_id: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(Text)
    sector: Mapped[str] = mapped_column(Text)
    sector_probability: Mapped[float] = mapped_column(Float)
    low_confidence: Mapped[bool] = mapped_column(Boolean)
    subgroup_id: Mapped[int] = mapped_column(Integer)
    subgroup_name: Mapped[str] = mapped_column(Text)
    margin: Mapped[float] = mapped_column(Float)
    ambiguous: Mapped[bool] = mapped_column(Boolean)
    n_words: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float)
    text_sha256: Mapped[str] = mapped_column(Text)


class ShadowPrediction(Base):
    """Operação: o que o modelo candidato teria respondido à mesma chamada, para comparar sem afetar o usuário."""

    __tablename__ = "shadow_predictions"
    __table_args__ = (Index("shadow_predictions_ts_idx", "ts"), {"schema": "ops"})

    id: Mapped[int] = mapped_column(BigId, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    request_id: Mapped[str] = mapped_column(Text)
    champion_version: Mapped[str] = mapped_column(Text)
    shadow_version: Mapped[str] = mapped_column(Text)
    champion_sector: Mapped[str] = mapped_column(Text)
    shadow_sector: Mapped[str] = mapped_column(Text)
    champion_subgroup: Mapped[str] = mapped_column(Text)
    shadow_subgroup: Mapped[str] = mapped_column(Text)
    shadow_latency_ms: Mapped[float] = mapped_column(Float)


class DriftCheck(Base):
    """Operação: o resultado de cada checagem de deriva."""

    __tablename__ = "drift_checks"
    __table_args__ = {"schema": "ops"}

    id: Mapped[int] = mapped_column(BigId, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    window_minutes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    calls: Mapped[int] = mapped_column(Integer)
    alerts: Mapped[list] = mapped_column(Json)
    measures: Mapped[dict] = mapped_column(Json)


class ModelBenchmark(Base):
    """Operação: linhas da comparação de modelos (triagem, busca de hiperparâmetros e teste), para o painel."""

    __tablename__ = "model_benchmark"
    __table_args__ = (Index("model_benchmark_stage_idx", "stage", "f1_macro"), {"schema": "ops"})

    id: Mapped[int] = mapped_column(BigId, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    stage: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    representation: Mapped[str | None] = mapped_column(Text)
    trial: Mapped[int | None] = mapped_column(Integer)
    f1_macro: Mapped[float | None] = mapped_column(Float)
    accuracy: Mapped[float | None] = mapped_column(Float)
    fit_seconds: Mapped[float | None] = mapped_column(Float)
    errors: Mapped[int | None] = mapped_column(Integer)
    ece: Mapped[float | None] = mapped_column(Float)
    parameters: Mapped[dict | None] = mapped_column(Json)


class SectorProfile(Base):
    """Ouro: resumo de cada setor (tamanho, duração, confiança da transcrição). Só agregados, nunca texto."""

    __tablename__ = "sector_profile"
    __table_args__ = {"schema": "gold"}

    sector: Mapped[str] = mapped_column(Text, primary_key=True)
    calls: Mapped[int] = mapped_column(Integer)
    words_p05: Mapped[float] = mapped_column(Float)
    words_p50: Mapped[float] = mapped_column(Float)
    words_p95: Mapped[float] = mapped_column(Float)
    duration_p50: Mapped[float] = mapped_column(Float)
    confidence_p50: Mapped[float] = mapped_column(Float)
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SizeHistogram(Base):
    """Ouro: quantas chamadas de cada setor cabem em cada faixa de palavras ou de confiança."""

    __tablename__ = "size_histogram"
    __table_args__ = {"schema": "gold"}

    sector: Mapped[str] = mapped_column(Text, primary_key=True)
    measure: Mapped[str] = mapped_column(Text, primary_key=True)
    bin_start: Mapped[float] = mapped_column(Float, primary_key=True)
    calls: Mapped[int] = mapped_column(Integer)


class HoldoutConfusion(Base):
    """Ouro: matriz de confusão de cada modelo no conjunto de teste (setor real contra setor previsto)."""

    __tablename__ = "holdout_confusion"
    __table_args__ = {"schema": "gold"}

    model_version: Mapped[str] = mapped_column(Text, primary_key=True)
    true_sector: Mapped[str] = mapped_column(Text, primary_key=True)
    predicted_sector: Mapped[str] = mapped_column(Text, primary_key=True)
    calls: Mapped[int] = mapped_column(Integer)


class SubgroupAnalysis(Base):
    """Ouro: medidas das análises de subgrupos do caderno (escolha de k, algoritmos, vizinhança, embeddings)."""

    __tablename__ = "subgroup_analysis"
    __table_args__ = {"schema": "gold"}

    id: Mapped[int] = mapped_column(BigId, primary_key=True)
    analysis: Mapped[str] = mapped_column(Text)
    sector: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    metric: Mapped[str] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Float)
