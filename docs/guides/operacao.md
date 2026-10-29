# Operação: retreinar, monitorar, voltar atrás

## Rotina

| Quando | O que roda | Quem agenda |
|---|---|---|
| toda segunda, 03:00 | `retrain_weekly`: ingest, train, promote, score | Airflow |
| a cada 15 minutos | `drift_check`: janela de 60 minutos da API contra a referência do modelo | Airflow |
| sob demanda | qualquer etapa, com `make <etapa>` | pessoa |

Sem Airflow, o mesmo com `cron`: `0 3 * * 1 cd /caminho && make ingest train promote score`.

## Entra dado novo

Coloque os arquivos novos em `data/<setor>/` e rode `make ingest`. A ingestão só acrescenta o que mudou (o que já entrou é reconhecido por caminho e hash), registra em `silver.quality_issues` o que foi rejeitado (arquivo vazio, cópia de um id existente, texto em branco) e cria uma nova versão do conjunto de dados em `gold.dataset_versions` se o conteúdo mudou. Chamadas novas caem em desenvolvimento ou teste por hash do texto, então o teste só cresce.

## Um modelo novo foi barrado: e agora?

`make promote` imprime o motivo e sai com código 3. Os casos:

| Motivo | O que fazer |
|---|---|
| os nomes dos subgrupos precisam de revisão | olhe os termos dos grupos novos (`python -c "..."` ou o painel de modelos), ajuste nomes e âncoras em `models/subgroup_names.json`, rode `make train promote` de novo |
| erra significativamente mais que o vigente | investigue os dados novos (a camada `quality_issues` e o painel de dados); não promova à força |
| latência acima do orçamento | veja `make latency`; o orçamento está em `settings.LATENCY_BUDGET_MS` |
| já é o vigente | nada a fazer |

## Ver um candidato em tráfego real antes de promover

1. Coloque o candidato no diretório de modelos (`models/challenger.joblib`).
2. Suba a API com `SHADOW_MODEL_PATH=/models/challenger.joblib`.
3. Depois de alguns dias, `make shadow-report` mostra a concordância de setor e de subgrupo e a latência do candidato; o painel `/operacao` mostra o mesmo por hora.

## Deriva

`make drift` (ou o DAG) compara a janela recente com a referência gravada em `segmenter.meta.json`. Com alerta, sai com código 1, grava em `ops.drift_checks` e avisa por Telegram (`--notify`, com `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`). A decisão sobre o que fazer é humana: normalmente conferir os dados da janela, e só então retreinar.

## Voltar a um modelo anterior

`models/archive/<versão>.joblib` guarda cada vigente que foi substituído. Copie o arquivo (e o `.meta.json` irmão) para `models/segmenter.joblib` e reinicie a API. Atualize `gold.model_versions` com `status = 'champion'` para a versão restaurada.

## Latência e capacidade

`make latency` mede a mediana, o p95 e o p99 de uma chamada isolada sobre chamadas reais de teste. O teste automatizado `tests/test_latency.py` falha se a mediana do modelo sintético passar do orçamento, para pegar regressão grosseira no CI.
