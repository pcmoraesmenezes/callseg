"""Regras de negócio da segmentação: chama o modelo, mede, monta a resposta e o registro de auditoria."""

import hashlib
import logging
import time
from dataclasses import asdict, dataclass

from call_segmenter import CallSegmenter
from call_segmenter.models.postprocessing import call_warnings
from call_segmenter.text import count_words

from .. import observability

log = logging.getLogger("segmenter")


def fingerprint(text: str) -> str:
    """Hash SHA-256 do texto: é o que se guarda no lugar da transcrição."""
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass
class SegmentationOutcome:
    """O que a API devolve para uma chamada e o que ela grava sobre ela."""

    response: dict
    prediction_row: dict


class SegmentationService:
    """Segmenta chamadas com o modelo vigente e, se houver, compara com um modelo candidato em sombra."""

    def __init__(self, segmenter: CallSegmenter, repository, shadow: CallSegmenter | None = None):
        self.segmenter = segmenter
        self.repository = repository
        self.shadow = shadow

    def segment(self, transcripts: list[str], request_id: str, explain: bool = False) -> list[SegmentationOutcome]:
        """Segmenta as transcrições e mede a latência média por chamada.

        Args:
            request_id: identificador da requisição; em lote, cada chamada recebe `<id>-<posição>`.
        """
        started = time.perf_counter()
        results = self.segmenter.predict(transcripts, explain=explain)
        per_call_seconds = (time.perf_counter() - started) / len(transcripts)
        outcomes = []
        for position, (text, result) in enumerate(zip(transcripts, results, strict=True)):
            call_request_id = request_id if len(transcripts) == 1 else f"{request_id}-{position}"
            outcome = self._outcome(text, result, call_request_id, per_call_seconds)
            self._count(outcome)
            outcomes.append(outcome)
        return outcomes

    def _outcome(self, text, result, request_id, per_call_seconds) -> SegmentationOutcome:
        word_count = count_words(text)
        latency_ms = round(per_call_seconds * 1000, 2)
        response = {
            "request_id": request_id,
            "model_version": self.segmenter.model_version,
            "sector": result.sector,
            "sector_probability": result.sector_probability,
            "sector_scores": result.sector_scores,
            "low_confidence": result.low_confidence,
            "subgroup": asdict(result.subgroup),
            "evidence": result.evidence,
            "warnings": call_warnings(word_count),
            "latency_ms": latency_ms,
        }
        row = {
            "request_id": request_id,
            "source": "api",
            "model_version": self.segmenter.model_version,
            "sector": result.sector,
            "sector_probability": result.sector_probability,
            "low_confidence": result.low_confidence,
            "subgroup_id": result.subgroup.id,
            "subgroup_name": result.subgroup.name,
            "margin": result.subgroup.margin,
            "ambiguous": result.subgroup.ambiguous,
            "n_words": word_count,
            "latency_ms": latency_ms,
            "text_sha256": fingerprint(text),
        }
        return SegmentationOutcome(response, row)

    def _count(self, outcome: SegmentationOutcome) -> None:
        row = outcome.prediction_row
        observability.REQUESTS.labels(row["sector"]).inc()
        observability.LATENCY.observe(row["latency_ms"] / 1000)
        if row["ambiguous"]:
            observability.AMBIGUOUS.labels(row["sector"]).inc()
        if row["low_confidence"]:
            observability.LOW_CONFIDENCE.inc()
        log.info(
            "segmentada",
            extra={
                "fields": {
                    key: row[key]
                    for key in (
                        "request_id",
                        "sector",
                        "sector_probability",
                        "subgroup_id",
                        "ambiguous",
                        "n_words",
                        "latency_ms",
                    )
                }
            },
        )

    def persist(self, transcripts: list[str], outcomes: list[SegmentationOutcome]) -> None:
        """Grava as predições e, havendo modelo candidato, a resposta dele à mesma chamada. Roda depois da resposta."""
        self.repository.save([outcome.prediction_row for outcome in outcomes])
        if self.shadow is not None:
            self.repository.save_shadow(self._shadow_rows(transcripts, outcomes))

    def _shadow_rows(self, transcripts: list[str], outcomes: list[SegmentationOutcome]) -> list[dict]:
        rows = []
        for text, outcome in zip(transcripts, outcomes, strict=True):
            started = time.perf_counter()
            shadow_result = self.shadow.predict([text])[0]
            shadow_ms = (time.perf_counter() - started) * 1000
            champion = outcome.prediction_row
            for field, differs in (
                ("sector", shadow_result.sector != champion["sector"]),
                ("subgroup", shadow_result.subgroup.name != champion["subgroup_name"]),
            ):
                if differs:
                    observability.SHADOW_DISAGREEMENT.labels(field).inc()
            rows.append(
                {
                    "request_id": champion["request_id"],
                    "champion_version": champion["model_version"],
                    "shadow_version": self.shadow.model_version,
                    "champion_sector": champion["sector"],
                    "shadow_sector": shadow_result.sector,
                    "champion_subgroup": champion["subgroup_name"],
                    "shadow_subgroup": shadow_result.subgroup.name,
                    "shadow_latency_ms": round(shadow_ms, 2),
                }
            )
        return rows
