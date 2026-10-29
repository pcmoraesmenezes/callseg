import numpy as np
import pytest

from call_segmenter import CallSegmenter
from call_segmenter.training import decide_promotion, evaluate_on_holdout, mcnemar_test
from conftest import CLUSTER_COUNTS
from synthetic import make_corpus


@pytest.fixture(scope="module")
def holdout():
    return make_corpus(per_topic=20, seed=99)


def test_holdout_report_counts_errors_and_calibration(segmenter, holdout):
    report = evaluate_on_holdout(segmenter, holdout)
    assert report.calls == len(holdout) and report.f1_macro > 0.95
    assert 0 <= report.expected_calibration_error <= 1 and report.errors == round((1 - report.accuracy) * report.calls)


def test_mcnemar_counts_only_the_calls_where_the_models_disagree():
    truth = np.array(["a", "a", "a", "a", "a", "a"])
    first = np.array(["a", "a", "b", "b", "a", "a"])
    second = np.array(["a", "b", "a", "a", "a", "a"])
    result = mcnemar_test(truth, first, second)
    assert (result["only_a_wrong"], result["only_b_wrong"]) == (2, 1)
    assert mcnemar_test(truth, first, first)["p_value"] == 1.0


def test_an_equivalent_candidate_is_promoted(segmenter, holdout, corpus, subgroup_catalog):
    twin = CallSegmenter(CLUSTER_COUNTS, subgroup_catalog, n_components=20, estimator="logreg").fit(corpus)
    twin.model_version += "-b"
    decision = decide_promotion(segmenter, twin, holdout)
    assert decision.promote and "não é pior" in decision.reason


def test_a_candidate_trained_on_shuffled_labels_is_blocked(segmenter, holdout, corpus, subgroup_catalog):
    broken_corpus = corpus.assign(sector=np.random.default_rng(0).permutation(corpus.sector.to_numpy()))
    broken = CallSegmenter(CLUSTER_COUNTS, estimator="logreg", n_components=20).fit(broken_corpus)
    decision = decide_promotion(segmenter, broken, holdout)
    assert not decision.promote and "erra significativamente mais" in decision.reason


def test_a_candidate_over_the_latency_budget_is_blocked(segmenter, holdout, corpus, subgroup_catalog):
    twin = CallSegmenter(CLUSTER_COUNTS, subgroup_catalog, n_components=20, estimator="logreg").fit(corpus)
    twin.model_version += "-b"
    decision = decide_promotion(segmenter, twin, holdout, latency_budget_ms=0.001)
    assert not decision.promote and "latência" in decision.reason


def test_a_candidate_whose_groups_do_not_match_the_names_is_blocked(segmenter, holdout, corpus, subgroup_catalog):
    wrong = {s: [{**e, "anchors": ["notinthevocabulary"]} for e in entries] for s, entries in subgroup_catalog.items()}
    unnamed = CallSegmenter(CLUSTER_COUNTS, wrong, n_components=20, estimator="logreg").fit(corpus)
    decision = decide_promotion(segmenter, unnamed, holdout)
    assert not decision.promote and "nomes dos subgrupos" in decision.reason


def test_promoting_the_model_that_is_already_champion_is_refused(segmenter, holdout):
    decision = decide_promotion(segmenter, segmenter, holdout)
    assert not decision.promote and "mesmo modelo" in decision.reason
