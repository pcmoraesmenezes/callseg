import json

from call_segmenter.data import assign_split, dataset_fingerprint, deduplicate_calls, read_transcripts


def write_call(directory, name, text, confidence=0.9):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(
        json.dumps(
            {
                "text": text,
                "confidence": confidence,
                "audio_duration": 200,
                "words": [{"text": word} for word in text.split()],
            }
        )
    )


def test_reading_skips_empty_files_and_flags_copies(tmp_path):
    write_call(tmp_path / "medicare", "aa11_transcript.json", "hello dog")
    write_call(tmp_path / "medicare", "aa11_transcript 2.json", "hello dog")
    (tmp_path / "medicare" / "bb22_transcript.json").write_bytes(b"")
    table = read_transcripts(tmp_path)
    assert sorted(table.file_name) == ["aa11_transcript 2.json", "aa11_transcript.json"]
    assert table.set_index("file_name").is_extra_copy.to_dict() == {
        "aa11_transcript.json": False,
        "aa11_transcript 2.json": True,
    }


def test_deduplication_keeps_the_original_file_and_drops_blank_text(tmp_path):
    write_call(tmp_path / "automotive", "cc33_transcript.json", "price of the car")
    write_call(tmp_path / "automotive", "cc33_transcript (1).json", "price of the car")
    write_call(tmp_path / "automotive", "dd44_transcript.json", "   ")
    calls = deduplicate_calls(read_transcripts(tmp_path))
    assert calls.file_name.tolist() == ["cc33_transcript.json"]


def test_split_is_stable_and_close_to_the_requested_fraction():
    keys = [f"text-{number}" for number in range(5000)]
    assert [assign_split(key) for key in keys] == [assign_split(key) for key in keys]
    share_in_test = sum(assign_split(key) == "test" for key in keys) / len(keys)
    assert 0.17 < share_in_test < 0.23


def test_fingerprint_changes_when_a_file_changes(tmp_path):
    write_call(tmp_path / "medicare", "aa11_transcript.json", "hello dog")
    before = dataset_fingerprint(tmp_path)["sha256"]
    write_call(tmp_path / "medicare", "aa11_transcript.json", "hello cat")
    assert dataset_fingerprint(tmp_path)["sha256"] != before
