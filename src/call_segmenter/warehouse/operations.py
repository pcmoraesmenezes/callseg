"""Acesso às tabelas de operação (predições da API, modo sombra, deriva) e ao registro de modelos."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from call_segmenter.monitoring.drift import DriftWindow

from .models import DriftCheck, ModelVersion, Prediction, ShadowPrediction

log = logging.getLogger("segmenter.warehouse")


class PredictionRepository:
    """Grava e consulta as predições. Falha de banco nunca derruba a resposta da API: é registrada no log."""

    enabled = True

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def save(self, rows: list[dict]) -> None:
        """Grava predições. Cada dict tem as colunas de `ops.predictions` (sem `id` e `ts`)."""
        self._write([Prediction(**row) for row in rows], "predição")

    def save_shadow(self, rows: list[dict]) -> None:
        """Grava as respostas do modelo candidato (ver `ShadowPrediction`)."""
        self._write([ShadowPrediction(**row) for row in rows], "predição em sombra")

    def _write(self, objects: list, what: str) -> None:
        try:
            with self.session_factory() as session:
                session.add_all(objects)
                session.commit()
        except SQLAlchemyError:
            log.exception("falha ao gravar %s", what)

    def recent(self, limit: int) -> list[dict]:
        """Últimas predições feitas pela API, da mais nova para a mais antiga."""
        try:
            with self.session_factory() as session:
                query = select(Prediction).where(Prediction.source == "api").order_by(Prediction.ts.desc()).limit(limit)
                return [
                    {
                        "ts": row.ts.isoformat(),
                        "sector": row.sector,
                        "sector_probability": row.sector_probability,
                        "subgroup": row.subgroup_name,
                        "ambiguous": row.ambiguous,
                    }
                    for row in session.scalars(query)
                ]
        except SQLAlchemyError:
            log.exception("falha ao ler predições")
            return []

    def dataset_sector_mix(self) -> dict[str, float]:
        """Participação de cada setor nas predições do conjunto de dados (a referência da mistura)."""
        with self.session_factory() as session:
            rows = session.execute(
                select(Prediction.sector, func.count())
                .where(Prediction.source == "dataset")
                .group_by(Prediction.sector)
            ).all()
        total = sum(count for _, count in rows) or 1
        return {sector: count / total for sector, count in rows}

    def window(self, minutes: int) -> DriftWindow:
        """Medidas das predições da API nos últimos `minutes` minutos."""
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        recent = (Prediction.source == "api") & (Prediction.ts > since)
        with self.session_factory() as session:
            calls, low_confidence, ambiguous, probability = session.execute(
                select(
                    func.count(),
                    func.coalesce(func.avg(case((Prediction.low_confidence, 1.0), else_=0.0)), 0.0),
                    func.coalesce(func.avg(case((Prediction.ambiguous, 1.0), else_=0.0)), 0.0),
                    func.coalesce(func.avg(Prediction.sector_probability), 0.0),
                ).where(recent)
            ).one()
            mix_rows = session.execute(
                select(Prediction.sector, func.count()).where(recent).group_by(Prediction.sector)
            ).all()
        mix = {sector: count / calls for sector, count in mix_rows} if calls else {}
        return DriftWindow(int(calls), float(low_confidence), float(ambiguous), float(probability), mix)

    def save_drift_check(self, window_minutes: int, status: str, calls: int, alerts: list[str], measures: dict) -> None:
        """Guarda o resultado de uma checagem de deriva."""
        self._write(
            [DriftCheck(window_minutes=window_minutes, status=status, calls=calls, alerts=alerts, measures=measures)],
            "checagem de deriva",
        )


class NullPredictionRepository:
    """Usado quando não há banco configurado: não grava nada e devolve listas vazias."""

    enabled = False

    def save(self, rows: list[dict]) -> None:
        pass

    def save_shadow(self, rows: list[dict]) -> None:
        pass

    def recent(self, limit: int) -> list[dict]:
        return []


class ModelRegistry:
    """Registro dos modelos treinados e de qual deles é o vigente (champion)."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def register(self, version: ModelVersion) -> None:
        """Insere ou atualiza o registro de uma versão de modelo."""
        with self.session_factory() as session:
            session.merge(version)
            session.commit()

    def champion(self) -> ModelVersion | None:
        """O modelo vigente, ou None se ainda não houver."""
        with self.session_factory() as session:
            return session.scalar(select(ModelVersion).where(ModelVersion.status == "champion"))

    def set_status(self, model_version: str, status: str, reason: str) -> None:
        """Muda o estado de um modelo. Ao promover, o vigente anterior passa a `retired`."""
        with self.session_factory() as session:
            if status == "champion":
                for old in session.scalars(select(ModelVersion).where(ModelVersion.status == "champion")):
                    old.status, old.status_reason = "retired", f"substituído por {model_version}"
            target = session.get(ModelVersion, model_version)
            target.status, target.status_reason = status, reason
            if status == "champion":
                target.promoted_at = datetime.now(timezone.utc)
            session.commit()
