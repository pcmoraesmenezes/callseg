"""Subgrupos dentro de um setor: KMeans sobre TF-IDF reduzido, com margem para atribuição frágil."""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from call_segmenter.text import mark_pii_tags

AMBIGUOUS_QUANTILE = 0.10
ANCHOR_TERMS_PER_CLUSTER = 30
TFIDF_SETTINGS = {
    "min_df": 5,
    "max_df": 0.4,
    "sublinear_tf": True,
    "ngram_range": (1, 2),
    "stop_words": "english",
    "max_features": 100_000,
}


@dataclass
class SubgroupAssignment:
    """Grupo atribuído a uma chamada e o quanto a atribuição é firme."""

    id: int
    name: str
    similarity: float
    margin: float
    ambiguous: bool
    runner_up: str


class SubgroupClusterer:
    """Descobre `n_clusters` tipos de chamada em um setor e atribui chamadas novas ao mais próximo."""

    def __init__(self, n_clusters: int, n_components: int = 100, seed: int = 0):
        self.n_clusters, self.n_components, self.seed = n_clusters, n_components, seed
        self.names = {cluster: f"grupo_{cluster}" for cluster in range(n_clusters)}
        self.anchors: dict[int, list[str]] = {}

    def fit(self, transcripts: list[str]) -> "SubgroupClusterer":
        """Ajusta vetorizador, redução de dimensão e KMeans sobre as transcrições do setor."""
        tfidf = self._fit_vectorizer(transcripts)
        self._fit_reducer(tfidf)
        vectors = self._to_unit_vectors(tfidf)
        self._fit_centroids(vectors)
        self._fit_ambiguity_margin(vectors)
        self._collect_top_terms(tfidf)
        return self

    def _fit_vectorizer(self, transcripts: list[str]):
        self.vectorizer = TfidfVectorizer(**TFIDF_SETTINGS)
        return self.vectorizer.fit_transform([mark_pii_tags(text) for text in transcripts])

    def _fit_reducer(self, tfidf) -> None:
        components = min(self.n_components, tfidf.shape[1] - 1)
        self.reducer = TruncatedSVD(components, random_state=self.seed).fit(tfidf)
        self.reducer.components_ = self.reducer.components_.astype(np.float32)

    def _to_unit_vectors(self, tfidf) -> np.ndarray:
        return normalize(self.reducer.transform(tfidf))

    def _fit_centroids(self, vectors: np.ndarray) -> None:
        kmeans = KMeans(self.n_clusters, n_init=10, random_state=self.seed).fit(vectors)
        self.labels_ = kmeans.labels_
        self.centroids = normalize(kmeans.cluster_centers_)

    def _fit_ambiguity_margin(self, vectors: np.ndarray) -> None:
        similarities = np.sort(vectors @ self.centroids.T, axis=1)
        margins = similarities[:, -1] - similarities[:, -2]
        self.margin_cut = float(np.quantile(margins, AMBIGUOUS_QUANTILE))

    def _collect_top_terms(self, tfidf) -> None:
        terms = np.array(self.vectorizer.get_feature_names_out())
        self.top_terms = {}
        for cluster in range(self.n_clusters):
            mean_weight = np.asarray(tfidf[self.labels_ == cluster].mean(axis=0)).ravel()
            self.top_terms[cluster] = terms[mean_weight.argsort()[::-1][:ANCHOR_TERMS_PER_CLUSTER]].tolist()

    @property
    def summary(self) -> list[dict]:
        """Catálogo dos grupos: id, nome, tamanho no treino e dez termos de maior peso."""
        return [
            {
                "id": cluster,
                "name": self.names[cluster],
                "size": int((self.labels_ == cluster).sum()),
                "top_terms": self.top_terms[cluster][:10],
            }
            for cluster in range(self.n_clusters)
        ]

    def name_clusters(self, catalog: list[dict]) -> None:
        """Dá nome aos grupos casando cada entrada do catálogo com o grupo que mais contém suas âncoras.

        Args:
            catalog: lista de `{"name": str, "anchors": [termos]}`, uma entrada por grupo.

        Raises:
            ValueError: se o catálogo tiver tamanho diferente de k ou algum nome ficar sem âncora no grupo.
        """
        if len(catalog) != self.n_clusters:
            raise ValueError(f"o catálogo tem {len(catalog)} nomes para {self.n_clusters} grupos")
        overlap = np.array(
            [
                [len(set(entry["anchors"]) & set(self.top_terms[cluster])) for cluster in range(self.n_clusters)]
                for entry in catalog
            ]
        )
        entry_rows, cluster_columns = linear_sum_assignment(-overlap)
        unanchored = [
            catalog[row]["name"]
            for row, column in zip(entry_rows, cluster_columns, strict=True)
            if overlap[row, column] == 0
        ]
        if unanchored:
            raise ValueError(f"nomes sem âncora no vocabulário do grupo: {unanchored}")
        for row, column in zip(entry_rows, cluster_columns, strict=True):
            self.names[int(column)] = catalog[row]["name"]
            self.anchors[int(column)] = catalog[row]["anchors"]

    def evidence_terms(self, transcript: str, cluster: int, top: int = 5) -> list[str]:
        """Termos de âncora do grupo que aparecem na chamada, na ordem do peso no grupo."""
        present = set(self.vectorizer.build_analyzer()(mark_pii_tags(transcript)))
        return [term for term in self.top_terms[cluster] if term in present][:top]

    def assign(self, transcripts: list[str]) -> list[SubgroupAssignment]:
        """Atribui cada chamada ao grupo de centro mais próximo."""
        tfidf = self.vectorizer.transform([mark_pii_tags(text) for text in transcripts])
        similarities = self._to_unit_vectors(tfidf) @ self.centroids.T
        ranking = np.argsort(similarities, axis=1)[:, ::-1]
        return [self._assignment(row, order) for row, order in zip(similarities, ranking, strict=True)]

    def _assignment(self, similarities: np.ndarray, ranking: np.ndarray) -> SubgroupAssignment:
        first, second = int(ranking[0]), int(ranking[1])
        margin = float(similarities[first] - similarities[second])
        return SubgroupAssignment(
            id=first,
            name=self.names[first],
            similarity=round(float(similarities[first]), 4),
            margin=round(margin, 4),
            ambiguous=margin < self.margin_cut,
            runner_up=self.names[second],
        )
