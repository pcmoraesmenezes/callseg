import random
import time

import pytest

from call_segmenter import settings
from synthetic import TOPICS, make_text

pytestmark = pytest.mark.latency


def timed_ms(function, repeats):
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        function()
        samples.append((time.perf_counter() - started) * 1000)
    return sorted(samples)


def test_segmenting_one_call_stays_inside_the_latency_budget(segmenter):
    text = make_text(random.Random(0), TOPICS["medicare"]["pet"], n=600)
    segmenter.predict([text])
    samples = timed_ms(lambda: segmenter.predict([text]), 60)
    assert samples[int(0.95 * len(samples))] < settings.LATENCY_BUDGET_MS


def test_the_api_answers_inside_twice_the_model_budget(client):
    payload = {"text": make_text(random.Random(2), TOPICS["home_service"]["vidro"], n=400)}
    client.post("/segment", json=payload)
    samples = timed_ms(lambda: client.post("/segment", json=payload), 40)
    assert samples[int(0.95 * len(samples))] < 2 * settings.LATENCY_BUDGET_MS
