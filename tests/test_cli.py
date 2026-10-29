import re
from pathlib import Path

from call_segmenter.cli import build_parser

DAG_FILE = Path(__file__).resolve().parents[1] / "airflow" / "dags" / "callseg_pipelines.py"


def subcommands() -> set[str]:
    actions = [action for action in build_parser()._actions if action.dest == "command"]
    return set(actions[0].choices)


def test_every_command_the_airflow_dag_calls_exists_in_the_cli():
    called = set(re.findall(r"\{CALLSEG\} ([a-z-]+)", DAG_FILE.read_text()))
    assert called and called <= subcommands()


def test_the_promote_gate_exit_code_matches_what_the_dag_skips_on():
    from call_segmenter.cli import NOT_PROMOTED

    assert f"NOT_PROMOTED_EXIT_CODE = {NOT_PROMOTED}" in DAG_FILE.read_text()


def test_the_parser_rejects_unknown_commands():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args(["nao-existe"])


def test_subgroup_rows_cover_every_analysis_in_metrics():
    import json

    from call_segmenter.pipelines.benchmark import subgroup_rows

    metrics_path = Path(__file__).resolve().parents[1] / "reports" / "metrics.json"
    rows = subgroup_rows(json.loads(metrics_path.read_text())["subgrupos"])
    assert {row.analysis for row in rows} == {"escolha_de_k", "algoritmos", "vizinhanca", "embeddings"}
    assert {row.sector for row in rows} == {"automotive", "home_service", "medicare"}
