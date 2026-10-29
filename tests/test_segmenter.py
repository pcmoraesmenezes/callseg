import random

import pytest

from call_segmenter import CallSegmenter
from conftest import CLUSTER_COUNTS
from synthetic import TOPICS, make_text


def test_routes_each_topic_to_its_sector(segmenter):
    generator = random.Random(7)
    for sector, topics in TOPICS.items():
        for words in topics.values():
            assert segmenter.predict([make_text(generator, words)])[0].sector == sector


def test_subgroup_comes_from_the_predicted_sector(segmenter):
    generator = random.Random(8)
    for sector, topics in TOPICS.items():
        for topic, words in topics.items():
            assert segmenter.predict([make_text(generator, words)])[0].subgroup.name == f"{sector}:{topic}"


def test_same_seed_gives_the_same_partition(corpus, segmenter, subgroup_catalog):
    again = CallSegmenter(CLUSTER_COUNTS, subgroup_catalog, n_components=20, estimator="logreg").fit(corpus)
    for sector in TOPICS:
        assert (again.clusterers[sector].labels_ == segmenter.clusterers[sector].labels_).all()
    assert again.model_version == segmenter.model_version


def test_naming_problems_are_recorded_and_the_groups_get_provisional_names(corpus, subgroup_catalog):
    wrong = {
        sector: [{**entry, "anchors": ["notinthevocabulary"]} for entry in entries]
        for sector, entries in subgroup_catalog.items()
    }
    segmenter = CallSegmenter(CLUSTER_COUNTS, wrong, n_components=20, estimator="logreg").fit(corpus)
    assert set(segmenter.naming_issues) == set(CLUSTER_COUNTS)
    assert segmenter.clusterers["medicare"].summary[0]["name"].startswith("grupo_")


def test_the_clusterer_refuses_a_catalog_with_the_wrong_size(corpus, subgroup_catalog):
    clusterer = CallSegmenter(CLUSTER_COUNTS, n_components=20, estimator="logreg").fit(corpus).clusterers["medicare"]
    with pytest.raises(ValueError, match="nomes para"):
        clusterer.name_clusters(subgroup_catalog["medicare"][:-1])


def test_naming_is_independent_of_the_order_of_the_catalog(corpus, subgroup_catalog):
    reversed_catalog = {sector: entries[::-1] for sector, entries in subgroup_catalog.items()}
    reordered = CallSegmenter(CLUSTER_COUNTS, reversed_catalog, n_components=20, estimator="logreg").fit(corpus)
    original = CallSegmenter(CLUSTER_COUNTS, subgroup_catalog, n_components=20, estimator="logreg").fit(corpus)
    assert [c["name"] for c in reordered.clusterers["medicare"].summary] == [
        c["name"] for c in original.clusterers["medicare"].summary
    ]


def test_the_margin_flags_roughly_the_training_quantile(segmenter, corpus):
    clusterer = segmenter.clusterers["medicare"]
    transcripts = corpus[corpus.sector == "medicare"].transcript.tolist()
    rate = sum(a.ambiguous for a in clusterer.assign(transcripts)) / len(transcripts)
    assert 0.05 <= rate <= 0.15


def test_evidence_terms_come_from_the_call_and_only_when_asked(segmenter):
    text = make_text(random.Random(5), TOPICS["medicare"]["pet"], n=150)
    assert segmenter.predict([text])[0].evidence is None
    evidence = segmenter.predict([text], explain=True)[0].evidence
    words = set(text.lower().split())
    assert evidence["sector_terms"] and all(set(term.split()) <= words for term in evidence["sector_terms"])
    assert evidence["subgroup_terms"]


def test_low_confidence_follows_the_configured_threshold(corpus, subgroup_catalog):
    strict = CallSegmenter(
        CLUSTER_COUNTS, subgroup_catalog, n_components=20, estimator="logreg", low_confidence_threshold=0.999999
    ).fit(corpus)
    text = make_text(random.Random(1), TOPICS["automotive"]["vendas"])
    assert strict.predict([text])[0].low_confidence is True


def test_save_and_load_keep_the_predictions(segmenter, tmp_path):
    segmenter.save(str(tmp_path / "model.joblib"))
    loaded = CallSegmenter.load(str(tmp_path / "model.joblib"))
    text = make_text(random.Random(2), TOPICS["home_service"]["fauna"])
    assert loaded.predict([text])[0] == segmenter.predict([text])[0]
