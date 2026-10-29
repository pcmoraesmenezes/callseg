# Guia da infraestrutura: o que cada arquivo faz

## `docker-compose.yml`

Um único arquivo descreve a pilha. Sem perfil, sobem `db`, `migrate` e `api`; o resto é opt-in por perfil:

| Perfil | O que sobe | Para que serve |
|---|---|---|
| (nenhum) | `db`, `migrate`, `api` | núcleo: banco, migrações e a API |
| `pipeline` | `pipeline` | roda **uma** etapa do ciclo do modelo e termina (`make ingest`, `train`, ...) |
| `bi` | `metabase`, `bi-proxy` | painéis e a página inicial com os atalhos |
| `bi-provision` | `bi-provision` | cria painéis e links públicos no Metabase (roda e termina) |
| `mlops` | `mlflow`, `mlflow-proxy` | servidor de experimentos atrás de senha |
| `mlops-log` | `mlflow-log` | registra execuções e modelo no MLflow (roda e termina) |
| `orchestration` | `airflow` | agenda retreino e deriva |

O `migrate` roda antes de qualquer serviço que use o banco: cria os bancos extras (Metabase, MLflow, Airflow), o papel de leitura do BI e aplica as migrações. Todos os contêineres de longa duração rodam sem privilégios (`no-new-privileges`, `cap_drop: ALL`), com limite de memória e, onde dá, sistema de arquivos somente leitura.

## Por que existe o `deploy/compose.prod.yml`

O `docker-compose.yml` **constrói** a imagem a partir do código, que é o que se quer em desenvolvimento e no CI. Em produção a imagem vem pronta do registro (GHCR) e o modelo vem de um diretório do servidor. O arquivo de produção só troca isso (imagem, volume do modelo e dos dados), e os dois são combinados: `docker compose -f docker-compose.yml -f deploy/compose.prod.yml ...`. Ver `deploy/README.md`.

## `Makefile`

Atalhos para comandos longos, sem lógica própria: `make help` lista todos. Os alvos do ciclo do modelo (`ingest`, `train`, `promote`, `score`, `drift`...) chamam `docker compose run --rm pipeline <etapa>`, a mesma coisa que o Airflow executa. Ele **não** só cria diretórios: é a porta de entrada de desenvolvimento, teste, subida da pilha, painéis e geração de documentos.

## `.pre-commit-config.yaml`

Ganchos que rodam antes de cada commit (instalar com `make hooks`): `ruff` (estilo e erros comuns) e uma trava que impede commitar dados, modelos treinados ou `.env`. É a primeira linha de defesa; o CI repete a checagem, porque gancho local pode ser pulado.

## `.env.example`

Modelo do `.env` (que fica fora do git): usuário e senha do banco, senha do leitor do BI, portas, conta do Metabase, hash da senha do MLflow, caminho do modelo candidato em sombra e credenciais do aviso por Telegram. Todo valor tem um padrão de desenvolvimento, e as senhas precisam ser trocadas.

## `docker/`

| Arquivo | O que é |
|---|---|
| `api.Dockerfile` | imagem da API **e** das etapas do pipeline (`callseg`). Duas fases: instala as dependências travadas com uv e copia só o ambiente pronto para a imagem final, que roda sem privilégios. Sem PyTorch, sem caderno, sem MLflow |
| `mlflow-server.Dockerfile` | o servidor MLflow, com metadados no PostgreSQL |
| `mlflow-client.Dockerfile` | o pacote do projeto mais o cliente MLflow, para `callseg mlflow-log` registrar o modelo (o cliente é pesado e não pertence à imagem da API) |
| `airflow.Dockerfile` | Airflow com o pacote em um ambiente à parte, para as bibliotecas de ciência de dados não brigarem com as dele |
| `caddy/mlflow.Caddyfile` | **Caddy** é um servidor web usado aqui como proxy reverso. Esta configuração põe autenticação básica na frente do MLflow, que não tem login próprio |
| `caddy/bi.Caddyfile` | serve a página inicial dos painéis e os atalhos curtos (`/dados`, `/modelos`, `/operacao`) e repassa o resto ao Metabase |

## `tools/`

Ferramentas de apoio, não etapas do pipeline: `provision_metabase.py` (idempotente: cria ou atualiza painéis), `build_diagrams.py`, `render_docs.py`, `build_slides.py`, `mlflow_credentials.sh`, `simulate_traffic.py` (envia chamadas reais para a API para demonstrar a deriva) e `build_fixture_model.py` (modelo sintético do CI).

## Banco de dados

O esquema é criado por migrações Alembic (`src/call_segmenter/warehouse/migrations/`). `docs/architecture/dados-em-camadas.png` mostra as camadas e `docs/adr/0009-dados-em-camadas.md` explica a escolha.
