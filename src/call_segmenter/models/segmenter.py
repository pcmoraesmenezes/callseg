"""Segmentador de chamadas: setor (supervisionado) e subgrupo dentro do setor (não supervisionado)."""

import hashlib
import json
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd

from .postprocessing import is_low_confidence
from .sector_classifier import build_sector_pipeline, terms_that_pushed_toward
from .subgroup_clusterer import SubgroupAssignment, SubgroupClusterer


@dataclass
class Segmentation:
    """Resultado da segmentação de uma chamada."""

    sector: str
    sector_probability: float
    sector_scores: dict[str, float]
    low_confidence: bool
    subgroup: SubgroupAssignment
    evidence: dict[str, list[str]] | None = None


class CallSegmenter:
    """Classifica o setor de uma chamada e atribui um subgrupo dentro do setor previsto."""

    def __init__(
        self,
        cluster_counts: dict[str, int],
        subgroup_catalog: dict[str, list[dict]] | None = None,
        seed: int = 0,
        n_components: int = 100,
        estimator: str = "svm_calibrated",
        regularization: float = 5.0,
        low_confidence_threshold: float = 0.9,
        tfidf_overrides: dict | None = None,
        estimator_params: dict | None = None,
    ):
        """
        Args:
            cluster_counts: número de subgrupos por setor.
            subgroup_catalog: nomes e âncoras dos subgrupos por setor (ver `SubgroupClusterer.name_clusters`).
            low_confidence_threshold: abaixo dessa probabilidade a chamada é marcada como baixa confiança.
        """
        self.cluster_counts = cluster_counts
        self.subgroup_catalog = subgroup_catalog or {}
        self.seed, self.n_components = seed, n_components
        self.estimator, self.regularization = estimator, regularization
        self.low_confidence_threshold = low_confidence_threshold
        self.tfidf_overrides, self.estimator_params = tfidf_overrides, estimator_params or {}

    def fit(self, calls: pd.DataFrame) -> "CallSegmenter":
        """Ajusta o classificador de setor e um agrupador por setor.

        Args:
            calls: tabela com as colunas `call_id`, `sector` e `transcript`, uma linha por chamada.
        """
        self.sector_classifier = build_sector_pipeline(
            self.estimator, self.regularization, self.tfidf_overrides, **self.estimator_params
        ).fit(calls.transcript, calls.sector)
        self.naming_issues: dict[str, str] = {}
        self.clusterers = {sector: self._fit_clusterer(sector, calls) for sector in self.cluster_counts}
        self.n_train = len(calls)
        self.model_version = self._version_of(calls)
        return self

    def _fit_clusterer(self, sector: str, calls: pd.DataFrame) -> SubgroupClusterer:
        clusterer = SubgroupClusterer(self.cluster_counts[sector], self.n_components, self.seed)
        clusterer.fit(calls[calls.sector == sector].transcript.tolist())
        if self.subgroup_catalog.get(sector):
            try:
                clusterer.name_clusters(self.subgroup_catalog[sector])
            except ValueError as error:
                # Um retreino pode desenhar grupos diferentes dos que os nomes descrevem; o modelo fica com
                # nomes provisórios e o portão de promoção exige revisão humana dos nomes.
                self.naming_issues[sector] = str(error)
        return clusterer

    def _version_of(self, calls: pd.DataFrame) -> str:
        """Versão = resumo dos dados (id e setor de cada chamada) e do catálogo de nomes, mais os parâmetros."""
        data = "".join(sorted(calls.call_id.astype(str) + ":" + calls.sector.astype(str)))
        data_digest = hashlib.sha256(data.encode()).hexdigest()[:8]
        names_digest = hashlib.sha256(json.dumps(self.subgroup_catalog, sort_keys=True).encode()).hexdigest()[:4]
        clusters = ".".join(str(count) for count in self.cluster_counts.values())
        return f"{data_digest}-{self.estimator}-k{clusters}-s{self.seed}-n{names_digest}"

    def predict(self, transcripts: list[str], explain: bool = False) -> list[Segmentation]:
        """Segmenta cada transcrição.

        Args:
            transcripts: textos completos das chamadas.
            explain: se True, inclui os termos que sustentam a decisão.

        Returns:
            Uma `Segmentation` por transcrição, na mesma ordem.
        """
        probabilities = self.sector_classifier.predict_proba(transcripts)
        return [self._segment(text, row, explain) for text, row in zip(transcripts, probabilities, strict=True)]

    def _segment(self, transcript: str, probabilities: np.ndarray, explain: bool) -> Segmentation:
        classes = self.sector_classifier.classes_
        sector = classes[int(probabilities.argmax())]
        subgroup = self.clusterers[sector].assign([transcript])[0]
        result = Segmentation(
            sector=sector,
            sector_probability=round(float(probabilities.max()), 4),
            sector_scores={name: round(float(value), 4) for name, value in zip(classes, probabilities, strict=True)},
            low_confidence=is_low_confidence(float(probabilities.max()), self.low_confidence_threshold),
            subgroup=subgroup,
        )
        if explain:
            result.evidence = {
                "sector_terms": terms_that_pushed_toward(self.sector_classifier, transcript, sector),
                "subgroup_terms": self.clusterers[sector].evidence_terms(transcript, subgroup.id),
            }
        return result

    def subgroup_catalog_summary(self) -> dict[str, list[dict]]:
        """Catálogo de subgrupos por setor, para exibir na API."""
        return {sector: clusterer.summary for sector, clusterer in self.clusterers.items()}

    def save(self, path: str) -> None:
        """Grava o modelo comprimido em `path`."""
        joblib.dump(self, path, compress=3)

    @staticmethod
    def load(path: str) -> "CallSegmenter":
        """Carrega um modelo gravado por `save`."""
        return joblib.load(path)
