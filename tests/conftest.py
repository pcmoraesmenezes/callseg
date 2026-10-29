import pytest

from call_segmenter import CallSegmenter
from synthetic import TOPICS, make_corpus

CLUSTER_COUNTS = {sector: len(topics) for sector, topics in TOPICS.items()}


@pytest.fixture(scope="session")
def corpus():
    return make_corpus()


@pytest.fixture(scope="session")
def subgroup_catalog(corpus):
    """Nome e âncora de cada grupo sintético, descobertos olhando o tópico que domina cada grupo."""
    probe = CallSegmenter(CLUSTER_COUNTS, n_components=20, estimator="logreg").fit(corpus)
    catalog = {}
    for sector, clusterer in probe.clusterers.items():
        topic_of_call = corpus[corpus.sector == sector].call_id.str.split("-").str[1].reset_index(drop=True)
        entries = []
        for cluster in range(clusterer.n_clusters):
            topic = topic_of_call[clusterer.labels_ == cluster].mode()[0]
            entries.append({"name": f"{sector}:{topic}", "anchors": [TOPICS[sector][topic].split()[0]]})
        catalog[sector] = entries
    return catalog


@pytest.fixture(scope="session")
def segmenter(corpus, subgroup_catalog):
    return CallSegmenter(CLUSTER_COUNTS, subgroup_catalog, n_components=20, estimator="logreg").fit(corpus)


@pytest.fixture(scope="session")
def model_path(segmenter, tmp_path_factory):
    path = tmp_path_factory.mktemp("model") / "segmenter.joblib"
    segmenter.save(str(path))
    return str(path)


@pytest.fixture
def client(model_path):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    with TestClient(create_app(Settings(model_path=model_path, database_url=None))) as test_client:
        yield test_client
