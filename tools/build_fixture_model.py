"""Treina um modelo pequeno com o corpus sintético dos testes. Serve ao CI e a demonstrações sem o dataset.

python tools/build_fixture_model.py models/segmenter.joblib
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from call_segmenter import CallSegmenter  # noqa: E402
from synthetic import TOPICS, make_corpus  # noqa: E402


def main(output: str) -> None:
    corpus = make_corpus()
    cluster_counts = {sector: len(topics) for sector, topics in TOPICS.items()}
    probe = CallSegmenter(cluster_counts, n_components=20, estimator="logreg").fit(corpus)
    catalog = {}
    for sector, clusterer in probe.clusterers.items():
        topic_of_call = corpus[corpus.sector == sector].call_id.str.split("-").str[1].reset_index(drop=True)
        catalog[sector] = []
        for cluster in range(clusterer.n_clusters):
            topic = topic_of_call[clusterer.labels_ == cluster].mode()[0]
            catalog[sector].append({"name": f"{sector}:{topic}", "anchors": [TOPICS[sector][topic].split()[0]]})
    CallSegmenter(cluster_counts, catalog, n_components=20, estimator="logreg").fit(corpus).save(output)


if __name__ == "__main__":
    main(sys.argv[1])
