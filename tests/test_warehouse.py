import json

import pytest
from sqlalchemy import select

from call_segmenter.warehouse import (
    Base,
    ModelRegistry,
    ModelVersion,
    PredictionRepository,
    create_db_engine,
    create_session_factory,
    ingest_directory,
    load_calls,
)
from call_segmenter.warehouse.models import QualityIssue


@pytest.fixture
def session_factory(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'warehouse.db'}")
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def write_call(directory, name, text):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(
        json.dumps(
            {"text": text, "confidence": 0.9, "audio_duration": 200, "words": [{"text": word} for word in text.split()]}
        )
    )


@pytest.fixture
def data_dir(tmp_path):
    root = tmp_path / "data"
    write_call(root / "medicare", "aa11_transcript.json", "dog boarding please")
    write_call(root / "medicare", "aa11_transcript 2.json", "dog boarding please now")
    write_call(root / "automotive", "bb22_transcript.json", "car price today")
    (root / "automotive").joinpath("cc33_transcript.json").write_bytes(b"")
    return root


def test_ingestion_builds_silver_and_records_what_it_rejected(session_factory, data_dir):
    with session_factory() as session:
        summary = ingest_directory(session, data_dir)
        assert (summary.files_seen, summary.files_new, summary.calls_added, summary.quality_issues) == (4, 4, 2, 2)
        assert sorted(load_calls(session).call_id) == ["aa11", "bb22"]
        assert sorted(issue.issue for issue in session.scalars(select(QualityIssue))) == [
            "arquivo_vazio",
            "copia_de_id_existente",
        ]


def test_ingesting_the_same_files_again_changes_nothing(session_factory, data_dir):
    with session_factory() as session:
        first = ingest_directory(session, data_dir)
        second = ingest_directory(session, data_dir)
    assert (second.files_new, second.calls_added, second.quality_issues) == (0, 0, 0)
    assert second.dataset_version_id == first.dataset_version_id


def test_new_files_create_a_new_dataset_version_and_keep_earlier_splits(session_factory, data_dir):
    with session_factory() as session:
        first = ingest_directory(session, data_dir)
        splits_before = load_calls(session).set_index("call_id").split.to_dict()
        write_call(data_dir / "home_service", "dd44_transcript.json", "window glass repair")
        second = ingest_directory(session, data_dir)
        splits_after = load_calls(session).set_index("call_id").split.to_dict()
    assert second.calls_added == 1 and second.dataset_version_id != first.dataset_version_id
    assert all(splits_after[call_id] == split for call_id, split in splits_before.items())


def test_prediction_repository_stores_hash_only_and_reports_window(session_factory):
    repository = PredictionRepository(session_factory)
    row = dict(
        request_id="r1",
        source="api",
        model_version="v1",
        sector="medicare",
        sector_probability=0.95,
        low_confidence=False,
        subgroup_id=1,
        subgroup_name="Pet",
        margin=0.3,
        ambiguous=True,
        n_words=120,
        latency_ms=5.0,
        text_sha256="a" * 64,
    )
    repository.save([row, {**row, "request_id": "r2", "ambiguous": False}])
    window = repository.window(60)
    assert window.calls == 2 and window.ambiguous_rate == 0.5 and window.sector_mix == {"medicare": 1.0}
    assert repository.recent(5)[0]["sector"] == "medicare"


def test_promoting_a_model_retires_the_previous_champion(session_factory):
    registry = ModelRegistry(session_factory)
    for version, status in (("v1", "champion"), ("v2", "challenger")):
        registry.register(
            ModelVersion(
                model_version=version,
                estimator="svm_calibrated",
                parameters={},
                metrics={},
                status=status,
                artifact_path=f"models/{version}.joblib",
            )
        )
    registry.set_status("v2", "champion", "passou no portão")
    assert registry.champion().model_version == "v2"
    with session_factory() as session:
        assert session.get(ModelVersion, "v1").status == "retired"


def test_a_byte_identical_copy_is_stored_as_a_file_and_flagged_as_a_copy(session_factory, data_dir):
    write_call(data_dir / "automotive", "bb22_transcript (1).json", "car price today")
    with session_factory() as session:
        summary = ingest_directory(session, data_dir)
        issues = [issue.issue for issue in session.scalars(select(QualityIssue))]
    assert summary.files_new == 5 and issues.count("copia_de_id_existente") == 2


def test_two_different_calls_with_identical_content_are_both_kept(session_factory, tmp_path):
    write_call(tmp_path / "automotive", "aa11_transcript.json", "same words")
    write_call(tmp_path / "automotive", "bb22_transcript.json", "same words")
    with session_factory() as session:
        summary = ingest_directory(session, tmp_path)
    assert summary.calls_added == 2
