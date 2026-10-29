# ADR 0008: orquestrar o ciclo do modelo com Airflow

**Estado:** aceito.

## Contexto
O ciclo do modelo tem etapas com dependência (só treina depois de ingerir; só promove depois de avaliar; só pontua se promoveu) e precisa rodar toda semana, além de uma checagem de deriva a cada 15 minutos. Uma versão anterior do projeto usava `make` e `cron` e não tinha orquestrador, o que fazia cada etapa parecer um script que roda uma vez.

## Decisão
Dois DAGs no Airflow (`airflow/dags/callseg_pipelines.py`): `retrain_weekly` (ingest, train, evaluate_and_promote, score) e `drift_check`. As tarefas só chamam o comando `callseg`; a lógica fica no pacote, onde tem teste. O código de saída 3 do `promote` ("não promovido") deixa a tarefa como pulada, sem acusar falha. O Airflow roda em contêiner próprio, com o pacote em um ambiente Python separado, para as dependências de ciência de dados não brigarem com as dele.

## Alternativas consideradas
- **`cron` mais `make`**: continua funcionando (é o que o Airflow executa por baixo) e é a alternativa quando o servidor não aguenta mais um serviço.
- **GitHub Actions agendado**: não enxerga o banco nem os arquivos do servidor.
- **Prefect ou Dagster**: equivalentes aqui; o Airflow é o que a maior parte das equipes já opera.

## Consequências
- Histórico de execuções, retentativas e alerta de falha de graça; o preço é um serviço a mais (cerca de 2 GB de memória).
- Trocar de orquestrador custa um arquivo, porque as tarefas são comandos.
