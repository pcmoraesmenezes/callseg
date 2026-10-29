.DEFAULT_GOAL := help
COMPOSE = docker compose
PIPELINE = $(COMPOSE) --profile pipeline run --rm pipeline

help: ## lista os comandos
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-22s %s\n", $$1, $$2}'

# Ambiente de desenvolvimento
install: ## cria o ambiente com uv (desenvolvimento, caderno e MLflow)
	uv sync --extra dev --extra notebook --extra mlops
hooks: ## liga o pre-commit
	uv run pre-commit install
lint: ## ruff
	uv run ruff check src backend tests tools airflow
format: ## formata o código com ruff
	uv run ruff format src backend tests tools airflow
test: ## testes (sem dataset, com modelo sintético)
	uv run pytest -q

# Pilha local
up: ## API, banco e migrações
	$(COMPOSE) up -d --build --wait
down: ## derruba tudo (os dados do banco ficam no volume)
	$(COMPOSE) --profile bi --profile mlops --profile orchestration down
logs: ## acompanha a API
	$(COMPOSE) logs -f api

# Ciclo de vida do modelo (cada alvo é uma etapa do pipeline; o Airflow chama as mesmas)
ingest: ## arquivos de data/ -> bronze -> prata -> versão dos dados
	$(PIPELINE) ingest data
train: ## treina o candidato em models/challenger.joblib
	$(PIPELINE) train
promote: ## avalia o candidato contra o vigente e promove se o portão deixar
	$(PIPELINE) promote
score: ## pontua as chamadas da prata com o modelo vigente
	$(PIPELINE) score
drift: ## compara a janela recente da API com a referência do modelo
	$(PIPELINE) drift --minutes 60
shadow-report: ## concordância entre o vigente e o candidato em sombra
	$(PIPELINE) shadow-report
latency: ## latência por chamada do modelo vigente
	$(PIPELINE) latency
load-benchmark: ## leva reports/benchmark.json (do caderno) para o painel
	$(PIPELINE) load-benchmark

# Painéis, MLflow e Airflow
bi-up: ## Metabase e página inicial dos painéis
	$(COMPOSE) --profile bi up -d --build --wait
bi-provision: ## cria painéis e links públicos no Metabase
	$(COMPOSE) --profile bi --profile bi-provision run --rm bi-provision
mlflow-up: ## servidor MLflow atrás de senha
	$(COMPOSE) --profile mlops up -d --build --wait
mlflow-login: ## gera senha e hash do MLflow (a senha vai para ~/.callseg_mlflow_login)
	bash tools/mlflow_credentials.sh
mlflow-log: ## registra a comparação de modelos e o modelo vigente no MLflow
	$(COMPOSE) --profile mlops --profile mlops-log run --rm --build mlflow-log
airflow-up: ## Airflow com os pipelines de retreino e de deriva
	$(COMPOSE) --profile orchestration up -d --build

export-aggregates: ## exporta agregados e predições (sem texto) para reports/export
	sh tools/export_aggregates.sh
import-aggregates: ## importa reports/export no banco deste ambiente
	sh tools/import_aggregates.sh

# Caderno, documentos e figuras
notebook: ## executa o caderno inteiro (horas; os passos lentos ficam em .cache/notebook)
	uv run jupyter execute --inplace notebooks/experimentacao.ipynb
docs: ## regenera o model card a partir de reports/metrics.json
	uv run python tools/render_docs.py
diagrams: ## regenera os diagramas de docs/architecture
	uv run python tools/build_diagrams.py
slides: ## regenera a apresentação
	uv run python tools/build_slides.py
manifest: ## impressão digital do dataset
	uv run python -c "import json,sys; from call_segmenter.data import dataset_fingerprint as f; print(json.dumps(f('data'), indent=1))" > docs/reports/data_manifest.json
