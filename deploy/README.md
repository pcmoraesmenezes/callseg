# Implantação

Como colocar a pilha de pé em um servidor Linux com Docker. Para rodar na própria máquina, veja o `README.md` da raiz.

## O que sobe

| Serviço | Porta (127.0.0.1) | Perfil do compose |
|---|---|---|
| API e página de demonstração | `API_PORT` (8010) | padrão |
| Painéis (Metabase atrás de um proxy) | `BI_PORT` (3010) | `bi` |
| MLflow atrás de senha | `MLFLOW_PORT` (5010) | `mlops` |
| Airflow | `AIRFLOW_PORT` (8080) | `orchestration` |
| PostgreSQL | só rede interna do compose | padrão |

Nenhum serviço publica porta fora do `127.0.0.1`. Para expor, coloque na frente um proxy reverso ou um túnel que aponte para essas portas (TLS e domínio ficam por conta dele).

## Passo a passo

1. **Usuário e Docker.** Rode o serviço com um usuário sem privilégios, de preferência com Docker em modo rootless: o grupo `docker` equivale a root, e um escape de contêiner chegaria só até esse usuário.
2. **Configuração.** `cp .env.example .env`, trocar todas as senhas e ajustar as portas. `chmod 600 .env`. Confira memória (`free -h`) e portas livres (`ss -ltn`): a pilha completa pede cerca de 4 GB.
3. **Modelo.** O modelo é derivado do dataset e não entra na imagem nem no git. Treine (`make train`, `make promote`) e copie `models/segmenter.joblib` e `models/segmenter.meta.json` para o diretório `MODELS_DIR` do servidor.
4. **Subir.** Com a imagem publicada pelo workflow `release`:
   ```bash
   export TAG=0.2.0 MODELS_DIR=$HOME/models DATA_DIR=$HOME/data
   docker compose -f docker-compose.yml -f deploy/compose.prod.yml --profile bi --profile mlops up -d --wait
   ```
   O serviço `migrate` cria os bancos e aplica as migrações antes de a API subir.
5. **Painéis.** `docker compose -f docker-compose.yml -f deploy/compose.prod.yml --profile bi-provision run --rm bi-provision` cria a fonte de dados, os três painéis, os links públicos e a página inicial.
6. **MLflow.** `make mlflow-login` gera a senha (o hash vai para o `.env`, a senha em texto para `~/.callseg_mlflow_login`, modo 600). Depois `make mlflow-log` registra a comparação de modelos e o modelo vigente.
7. **Agregados do conjunto de dados.** O dataset não vai para o servidor; só agregados e predições (sem texto). Na máquina onde o pipeline rodou: `make export-aggregates` gera `reports/export/*.csv`; copie a pasta para o servidor e rode `make import-aggregates` no diretório do compose (substitui as linhas anteriores dessas tabelas). Reprovisione os painéis depois.
8. **Agendamento.** Com o perfil `orchestration` o Airflow agenda o retreino semanal e a checagem de deriva. Sem ele, o equivalente é um `cron` que chama `docker compose run --rm pipeline <etapa>`.

## Atualizar

- **Código:** nova tag `vX.Y.Z` publica a imagem; o workflow `deploy` (execução manual, runner no servidor) baixa essa versão e reinicia só o que mudou.
- **Modelo:** o `promote` troca o `segmenter.joblib` e guarda o anterior em `models/archive`; reinicie a API para carregá-lo.
- **Voltar atrás:** copie o arquivo de `models/archive/<versão>.joblib` de volta para `segmenter.joblib` (e o `.meta.json` irmão).

## Exposição pública e senhas

- API e painéis são abertos por decisão de projeto (ADR 0012): só devolvem classificação do texto enviado pelo próprio visitante e agregados. O texto nunca é gravado.
- O MLflow não tem login e quem entra apaga execuções e modelos: só o proxy dele publica porta, com autenticação básica.
- A conta de administração do Metabase fica acessível pela mesma URL dos painéis públicos: use senha forte e mantenha o cadastro desligado.

## Derrubar

`docker compose --profile bi --profile mlops --profile orchestration down -v` apaga contêineres e volumes (inclui o banco). Sem `-v` os dados ficam.
