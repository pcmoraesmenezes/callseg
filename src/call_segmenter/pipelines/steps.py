"""Etapas do ciclo de vida do modelo. Cada função faz uma coisa e pode ser chamada pela CLI ou por um orquestrador."""

import json
import logging
import os
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from call_segmenter import settings
from call_segmenter.data import dataset_fingerprint
from call_segmenter.models import CallSegmenter
from call_segmenter.monitoring import evaluate_window
from call_segmenter.training import decide_promotion, evaluate_on_holdout, train_segmenter
from call_segmenter.training.reference import compute_drift_baseline
from call_segmenter.warehouse import ModelRegistry, ModelVersion, PredictionRepository, ingest_directory, load_calls
from call_segmenter.warehouse.gold import build_sector_aggregates, record_holdout_confusion
from call_segmenter.warehouse.models import DatasetVersion, Prediction, ShadowPrediction

from .artifacts import archive_and_replace, baseline_as_dict, baseline_of, read_metadata, save_model

log = logging.getLogger("segmenter.pipeline")


def ingest(session_factory, data_dir: str) -> dict:
    """Etapa 1. Arquivos -> bronze -> prata -> versão do conjunto de dados."""
    with session_factory() as session:
        summary = ingest_directory(session, data_dir)
        build_sector_aggregates(session)
    return {**summary.__dict__, "fingerprint": dataset_fingerprint(data_dir)["sha256"]}


def train_challenger(session_factory, output_path: str) -> dict:
    """Etapa 2. Treina com as chamadas de desenvolvimento da prata e grava o candidato com seus metadados."""
    with session_factory() as session:
        development = load_calls(session, "development")
        version = session.scalar(select(DatasetVersion).order_by(DatasetVersion.id.desc()))
    segmenter = train_segmenter(development)
    baseline = compute_drift_baseline(development, segmenter)
    save_model(
        segmenter,
        output_path,
        {
            "dataset_version_id": version.id if version else None,
            "dataset_sha256": version.data_sha256 if version else None,
            "drift_baseline": baseline_as_dict(baseline),
        },
    )
    return {"model_version": segmenter.model_version, "n_train": segmenter.n_train, "path": output_path}


def evaluate_candidate(session_factory, champion_path: str, challenger_path: str) -> dict:
    """Etapa 3. Compara candidato e vigente no conjunto de teste e decide se o candidato pode entrar."""
    with session_factory() as session:
        holdout = load_calls(session, "test")
    champion = CallSegmenter.load(champion_path) if Path(champion_path).exists() else None
    challenger = CallSegmenter.load(challenger_path)
    report = evaluate_on_holdout(challenger, holdout).to_dict()
    probabilities = challenger.sector_classifier.predict_proba(holdout.transcript.tolist())
    predicted = pd.Series(challenger.sector_classifier.classes_[probabilities.argmax(axis=1)])
    with session_factory() as session:
        record_holdout_confusion(session, challenger.model_version, holdout.sector, predicted)
    decision = decide_promotion(champion, challenger, holdout)
    return {**decision.__dict__, "challenger": report}


def promote_candidate(
    session_factory, champion_path: str, challenger_path: str, decision: dict, archive_dir: str
) -> str:
    """Etapa 4. Registra o candidato e, se o portão deixou, troca o vigente (guardando o antigo)."""
    metadata = read_metadata(challenger_path)
    registry = ModelRegistry(session_factory)
    status = "champion" if decision["promote"] or decision.get("already_champion") else "rejected"
    registry.register(
        ModelVersion(
            model_version=metadata["model_version"],
            dataset_version_id=metadata.get("dataset_version_id"),
            estimator=metadata["estimator"],
            parameters={"cluster_counts": settings.CLUSTER_COUNTS},
            metrics=decision["challenger"],
            status="challenger",
            artifact_path=str(challenger_path),
        )
    )
    registry.set_status(metadata["model_version"], status, decision["reason"])
    if decision["promote"]:
        archive_and_replace(challenger_path, champion_path, archive_dir)
    return status


def score_dataset(session_factory, model_path: str, batch_size: int = 200) -> int:
    """Pontua as chamadas da prata e grava em `ops.predictions` com `source = 'dataset'`, trocando as anteriores."""
    segmenter = CallSegmenter.load(model_path)
    with session_factory() as session:
        calls = load_calls(session)
        session.query(Prediction).filter(Prediction.source == "dataset").delete()
        _score_in_batches(session, segmenter, calls, batch_size)
    return len(calls)


def _score_in_batches(session, segmenter, calls, batch_size):
    for start in range(0, len(calls), batch_size):
        chunk = calls.iloc[start : start + batch_size]
        results = segmenter.predict(chunk.transcript.tolist())
        session.add_all(
            [
                Prediction(
                    request_id=f"{segmenter.model_version}-{call_id}",
                    source="dataset",
                    model_version=segmenter.model_version,
                    sector=result.sector,
                    sector_probability=result.sector_probability,
                    low_confidence=result.low_confidence,
                    subgroup_id=result.subgroup.id,
                    subgroup_name=result.subgroup.name,
                    margin=result.subgroup.margin,
                    ambiguous=result.subgroup.ambiguous,
                    n_words=int(words),
                    latency_ms=0.0,
                    text_sha256=digest,
                )
                for call_id, words, digest, result in zip(
                    chunk.call_id, chunk.word_count, chunk.text_sha256, results, strict=True
                )
            ]
        )
        session.commit()


def check_drift(session_factory, model_path: str, minutes: int) -> dict:
    """Compara as predições da API na janela com a referência gravada junto do modelo e guarda o resultado."""
    repository = PredictionRepository(session_factory)
    report = evaluate_window(baseline_of(model_path), repository.window(minutes))
    repository.save_drift_check(minutes, report.status, report.calls, report.alerts, report.measures)
    return {
        "status": report.status,
        "calls": report.calls,
        "alerts": report.alerts,
        "measures": report.measures,
        "window_minutes": minutes,
    }


def notify_telegram(alerts: list[str]) -> None:
    """Avisa por Telegram quando `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` estão definidos."""
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": "Deriva no segmentador:\n" + "\n".join(alerts)}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=15)


def shadow_report(session_factory, days: int) -> dict:
    """Concordância entre o vigente e o candidato em sombra nos últimos `days` dias."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with session_factory() as session:
        rows = session.execute(
            select(
                ShadowPrediction.champion_sector == ShadowPrediction.shadow_sector,
                ShadowPrediction.champion_subgroup == ShadowPrediction.shadow_subgroup,
                ShadowPrediction.shadow_latency_ms,
            ).where(ShadowPrediction.ts > since)
        ).all()
    if not rows:
        return {"calls": 0}
    return {
        "calls": len(rows),
        "sector_agreement": sum(r[0] for r in rows) / len(rows),
        "subgroup_agreement": sum(r[1] for r in rows) / len(rows),
        "shadow_latency_ms_median": statistics.median(r[2] for r in rows),
    }


def measure_latency(model_path: str, transcripts: list[str], repeats: int = 3) -> dict:
    """Latência de segmentar uma chamada isolada, em milissegundos: mediana, p95 e p99."""
    segmenter = CallSegmenter.load(model_path)
    samples = []
    for _ in range(repeats):
        for text in transcripts:
            started = time.perf_counter()
            segmenter.predict([text])
            samples.append((time.perf_counter() - started) * 1000)
    samples.sort()
    pick = lambda quantile: samples[min(len(samples) - 1, int(quantile * len(samples)))]  # noqa: E731
    return {
        "calls": len(samples),
        "p50_ms": round(pick(0.5), 2),
        "p95_ms": round(pick(0.95), 2),
        "p99_ms": round(pick(0.99), 2),
    }


def dump(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=1, default=str)
