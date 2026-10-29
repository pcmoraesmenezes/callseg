"""Linha de comando `callseg`: um comando por etapa do ciclo de vida do modelo.

    callseg migrate | ingest | train | evaluate | promote | score | drift | shadow-report | latency
            load-benchmark | mlflow-log

Todos leem `DATABASE_URL` do ambiente quando precisam do banco. A saída é sempre JSON, para um orquestrador ler.
"""

import argparse
import json
import os
import sys

from call_segmenter.pipelines import steps
from call_segmenter.warehouse import create_db_engine, create_session_factory, load_calls
from call_segmenter.warehouse.bootstrap import prepare_cluster, upgrade_schema

DEFAULT_CHAMPION = "models/segmenter.joblib"
DEFAULT_CHALLENGER = "models/challenger.joblib"
DEFAULT_ARCHIVE = "models/archive"
NOT_PROMOTED = 3


def session_factory():
    return create_session_factory(create_db_engine(os.environ["DATABASE_URL"]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="callseg", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("migrate", help="cria os bancos e o papel do BI e aplica as migrações")
    ingest = commands.add_parser("ingest", help="arquivos -> bronze -> prata -> versão do conjunto de dados")
    ingest.add_argument("data_dir")
    train = commands.add_parser("train", help="treina o candidato com as chamadas de desenvolvimento")
    train.add_argument("--output", default=DEFAULT_CHALLENGER)
    for name, text in (
        ("evaluate", "compara candidato e vigente no teste (não altera nada)"),
        ("promote", "avalia e, se o portão deixar, troca o vigente. Sai com código 3 se não promover"),
    ):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("--champion", default=DEFAULT_CHAMPION)
        sub.add_argument("--challenger", default=DEFAULT_CHALLENGER)
        if name == "promote":
            sub.add_argument("--archive-dir", default=DEFAULT_ARCHIVE)
    score = commands.add_parser("score", help="pontua as chamadas da prata e grava em ops.predictions")
    score.add_argument("--model", default=DEFAULT_CHAMPION)
    drift = commands.add_parser("drift", help="compara a janela recente da API com a referência do modelo")
    drift.add_argument("--model", default=DEFAULT_CHAMPION)
    drift.add_argument("--minutes", type=int, default=60)
    drift.add_argument("--notify", action="store_true", help="avisa por Telegram quando há alerta")
    shadow = commands.add_parser("shadow-report", help="concordância entre vigente e candidato em sombra")
    shadow.add_argument("--days", type=int, default=7)
    benchmark = commands.add_parser("load-benchmark", help="leva o benchmark.json do caderno para ops.model_benchmark")
    benchmark.add_argument("path", nargs="?", default="reports/benchmark.json")
    mlflow = commands.add_parser("mlflow-log", help="registra a comparação de modelos e o modelo vigente no MLflow")
    mlflow.add_argument("--model", default=DEFAULT_CHAMPION)
    mlflow.add_argument("--benchmark", default="reports/benchmark.json")
    mlflow.add_argument("--figures", default="reports/figures")
    latency = commands.add_parser("latency", help="mede a latência por chamada em chamadas de teste")
    latency.add_argument("--model", default=DEFAULT_CHAMPION)
    latency.add_argument("--calls", type=int, default=60)
    return parser


def run(arguments: argparse.Namespace) -> tuple[dict, int]:
    """Executa o comando e devolve (resultado, código de saída)."""
    if arguments.command == "migrate":
        url = os.environ["DATABASE_URL"]
        prepare_cluster(
            os.environ.get("ADMIN_DATABASE_URL", url), os.environ["BI_PASSWORD"], url.rsplit("/", 1)[1].split("?")[0]
        )
        upgrade_schema(url)
        return {"migrated": True}, 0
    factory = session_factory()
    if arguments.command == "ingest":
        return steps.ingest(factory, arguments.data_dir), 0
    if arguments.command == "train":
        return steps.train_challenger(factory, arguments.output), 0
    if arguments.command in ("evaluate", "promote"):
        decision = steps.evaluate_candidate(factory, arguments.champion, arguments.challenger)
        if arguments.command == "evaluate":
            return decision, 0
        status = steps.promote_candidate(
            factory, arguments.champion, arguments.challenger, decision, arguments.archive_dir
        )
        return {**decision, "status": status}, 0 if decision["promote"] else NOT_PROMOTED
    if arguments.command == "score":
        return {"scored_calls": steps.score_dataset(factory, arguments.model)}, 0
    if arguments.command == "drift":
        report = steps.check_drift(factory, arguments.model, arguments.minutes)
        if report["alerts"] and arguments.notify:
            steps.notify_telegram(report["alerts"])
        return report, 1 if report["alerts"] else 0
    if arguments.command == "load-benchmark":
        from pathlib import Path

        from call_segmenter.pipelines.benchmark import load_benchmark, load_subgroup_analysis

        metrics_path = Path(arguments.path).with_name("metrics.json")
        return {
            "rows": load_benchmark(factory, arguments.path),
            "subgroup_rows": load_subgroup_analysis(factory, str(metrics_path)),
        }, 0
    if arguments.command == "mlflow-log":
        from call_segmenter.pipelines.mlflow_logging import log_all

        return log_all(arguments.model, arguments.benchmark, arguments.figures), 0
    if arguments.command == "shadow-report":
        return steps.shadow_report(factory, arguments.days), 0
    with factory() as session:
        sample = load_calls(session, "test").sample(arguments.calls, random_state=0).transcript.tolist()
    return steps.measure_latency(arguments.model, sample), 0


def main() -> None:
    result, exit_code = run(build_parser().parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
