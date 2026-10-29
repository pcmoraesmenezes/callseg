import logging
import random

from synthetic import TOPICS, make_text


def sample(sector, topic=None):
    generator = random.Random(3)
    words = TOPICS[sector][topic or next(iter(TOPICS[sector]))]
    return {"text": make_text(generator, words, n=150), "words": [{"text": "ignored"}], "confidence": 0.9}


def test_accepts_dataset_shaped_json_and_returns_sector_and_subgroup(client):
    for sector in TOPICS:
        response = client.post("/segment", json=sample(sector))
        assert response.status_code == 200
        body = response.json()
        assert body["sector"] == sector
        assert body["subgroup"]["name"].startswith(sector)
        assert abs(sum(body["sector_scores"].values()) - 1) < 1e-3
        assert body["request_id"] == response.headers["X-Request-ID"]


def test_blank_and_oversized_text_are_rejected(client):
    assert client.post("/segment", json={"text": "   "}).status_code == 422
    assert client.post("/segment", json={"text": "a " * 150_000}).status_code == 422


def test_a_short_call_gets_a_warning(client):
    response = client.post("/segment", json={"text": "my dog needs boarding next week"})
    assert response.json()["warnings"] == ["transcricao_curta"]


def test_batch_keeps_order_and_enforces_the_limit(client):
    calls = [sample("medicare"), sample("automotive")]
    response = client.post("/segment/batch", json={"calls": calls})
    assert [item["sector"] for item in response.json()] == ["medicare", "automotive"]
    assert len({item["request_id"] for item in response.json()}) == 2
    assert client.post("/segment/batch", json={"calls": [calls[0]] * 51}).status_code == 422


def test_catalog_lists_every_subgroup_with_its_size(client):
    catalog = client.get("/subgroups").json()
    assert {sector: len(groups) for sector, groups in catalog.items()} == {
        sector: len(topics) for sector, topics in TOPICS.items()
    }
    assert all(group["size"] > 0 for groups in catalog.values() for group in groups)


def test_health_reports_the_model_version(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["model_version"] and body["prediction_log"] is False
    assert 0 < body["sector_min_probability"] < 1 and body["shadow_model_version"] is None


def test_the_prediction_log_stores_metadata_and_never_the_text(client):
    saved = []

    class Spy:
        enabled = True

        def save(self, rows):
            saved.extend(rows)

        def save_shadow(self, rows):
            pass

        def recent(self, limit):
            return []

    payload = sample("home_service")
    client.app.state.service.repository = Spy()
    client.post("/segment", json=payload)
    assert len(saved) == 1
    row = saved[0]
    assert payload["text"] not in str(row.values())
    assert len(row["text_sha256"]) == 64 and row["source"] == "api" and row["n_words"] == 150


def test_the_shadow_model_answers_in_the_background_without_changing_the_response(client, segmenter):
    shadow_rows = []

    class Spy:
        enabled = True

        def save(self, rows):
            pass

        def save_shadow(self, rows):
            shadow_rows.extend(rows)

        def recent(self, limit):
            return []

    service = client.app.state.service
    service.repository, service.shadow = Spy(), segmenter
    response = client.post("/segment", json=sample("medicare"))
    assert response.status_code == 200 and response.json()["model_version"] == segmenter.model_version
    assert len(shadow_rows) == 1 and shadow_rows[0]["champion_sector"] == shadow_rows[0]["shadow_sector"]


def test_metrics_endpoint_counts_requests(client):
    client.post("/segment", json=sample("automotive"))
    assert "segment_requests_total" in client.get("/metrics").text


def test_the_front_end_is_served(client):
    response = client.get("/demo/")
    assert response.status_code == 200 and "Callseg" in response.text
    assert client.get("/demo/app.js").status_code == 200 and client.get("/demo/favicon.svg").status_code == 200


def test_logs_never_contain_the_transcript(client, caplog):
    payload = sample("medicare")
    with caplog.at_level(logging.INFO, logger="segmenter"):
        client.post("/segment", json=payload)
    assert caplog.records
    assert all(payload["text"][:60] not in record.getMessage() for record in caplog.records)
    assert all(payload["text"][:60] not in str(getattr(record, "fields", "")) for record in caplog.records)


def test_explain_returns_terms_from_the_call_only_when_asked(client):
    call = sample("medicare")
    assert client.post("/segment", json=call).json()["evidence"] is None
    evidence = client.post("/segment?explain=true", json=call).json()["evidence"]
    words = set(call["text"].lower().split())
    assert evidence["sector_terms"] and all(set(term.split()) <= words for term in evidence["sector_terms"])
    assert evidence["subgroup_terms"]
