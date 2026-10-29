"""Pipelines do segmentador de chamadas.

`retrain_weekly` ingere os arquivos novos, treina um candidato, compara com o modelo vigente no conjunto de teste e
promove se o portão deixar. `drift_check` compara as predições recentes da API com a referência do modelo.

As tarefas só chamam o comando `callseg`; a lógica mora no pacote, onde tem teste.
"""

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

CALLSEG = "/opt/callseg/bin/callseg"
DATA_DIR = os.environ.get("CALLSEG_DATA_DIR", "/srv/data")
NOT_PROMOTED_EXIT_CODE = 3

default_args = {"owner": "ciencia-de-dados", "retries": 1, "retry_delay": timedelta(minutes=10)}

with DAG(
    "retrain_weekly",
    description="Dados novos -> candidato -> portão de promoção -> pontuação",
    schedule="0 3 * * 1",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["callseg", "treino"],
) as retrain_weekly:
    ingest = BashOperator(task_id="ingest_new_files", bash_command=f"{CALLSEG} ingest {DATA_DIR}")
    train = BashOperator(task_id="train_challenger", bash_command=f"{CALLSEG} train --output models/challenger.joblib")
    # Código 3 é "não promovido" e não é falha: a tarefa fica como pulada e o vigente continua valendo.
    promote = BashOperator(
        task_id="evaluate_and_promote",
        bash_command=f"{CALLSEG} promote",
        skip_on_exit_code=NOT_PROMOTED_EXIT_CODE,
    )
    score = BashOperator(task_id="score_dataset", bash_command=f"{CALLSEG} score")
    ingest >> train >> promote >> score

with DAG(
    "drift_check",
    description="Compara a janela recente da API com a referência do modelo vigente",
    schedule="*/15 * * * *",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    default_args={**default_args, "retries": 0},
    tags=["callseg", "monitoramento"],
) as drift_check:
    BashOperator(
        task_id="check_drift",
        bash_command=f"{CALLSEG} drift --minutes 60 --notify",
        skip_on_exit_code=None,
    )
