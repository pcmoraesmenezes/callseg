# Pré-mortem: o que pode dar errado e o que pega

Cada risco aponta para o mecanismo que o detecta. Prosa não é trava: o que importa é a coluna "Pega por".

| # | Risco | Pega por |
|---|---|---|
| 1 | O nome de um subgrupo mente depois de retreinar (os grupos mudam de desenho) | Termos-âncora por nome: se faltarem no grupo, o modelo fica com nomes provisórios e o portão de promoção o barra (`tests/test_segmenter.py`, `tests/test_training.py`, ADR 0003) |
| 2 | Um retreino automático põe em produção um modelo pior | Portão: McNemar contra o vigente no teste fixo, orçamento de latência, nomes (ADR 0014) |
| 3 | O conjunto de teste muda entre versões e as comparações deixam de valer | A divisão sai do hash do texto da chamada; o teste só cresce (`tests/test_data.py`, `tests/test_warehouse.py`) |
| 4 | Vazamento por chamada repetida entre treino e teste | Divisão por grupo de texto idêntico; a prata registra cada cópia em `quality_issues`; o caderno mede o efeito (seção 3) |
| 5 | O modelo "acerta" por atalho (metadados, marcadores, roteiro de abertura) | Testes de vazamento no caderno, com rótulos embaralhados como prova de sanidade |
| 6 | Texto de chamada no log ou no banco | `test_the_prediction_log_stores_metadata_and_never_the_text`, `test_logs_never_contain_the_transcript`; o painel lê só ouro e operação |
| 7 | Dataset, modelo treinado ou segredo entra no git | `.gitignore`, o gancho do pre-commit e a checagem do CI |
| 8 | Número errado em documento ou slide | `reports/metrics.json` é a fonte única; `make docs` e `make slides` leem dele, nada é digitado à mão |
| 9 | Pickle de uma versão de biblioteca carregado em outra | `uv.lock` e imagem com as mesmas versões; o CI treina o modelo de teste dentro do ambiente da imagem |
| 10 | O Metabase escreve ou apaga dado | Papel `bi_reader` só com `SELECT`; o CI confirma que `DELETE` é negado |
| 11 | Deriva sem ninguém ver | `drift_check` a cada 15 minutos, resultado em `ops.drift_checks`, aviso por Telegram (`tests/test_drift.py`) |
| 12 | Reingerir os mesmos arquivos duplica dado | Bronze identifica arquivo por caminho e hash; teste de idempotência (`tests/test_warehouse.py`) |
| 13 | Migração de banco quebra o servidor que já tem dados | A migração inicial move `public.predictions` para `ops` sem perder linhas; testada contra um banco antigo |
| 14 | A API aceita entrada gigante e trava | `max_length` no texto, limite de lote, `mem_limit` do contêiner (`test_blank_and_oversized_text_are_rejected`) |
| 15 | A latência passa do aceitável | `tests/test_latency.py` no CI e `callseg latency` sobre chamadas reais; orçamento no portão |
| 16 | O servidor da demonstração sofre com outros serviços | Projeto compose próprio, rede própria, `mem_limit`, `cap_drop: ALL`, usuário sem privilégio |
| 17 | A demonstração cai | Capturas dos painéis e do front na apresentação |
| 18 | Dado de terceiros publicado por engano | Repositório privado até revisão; `data/` e `models/` fora do git e da imagem; bronze e prata nunca vão para o servidor público |

## Antes de cada apresentação
1. `make test` e `make lint` verdes.
2. `docker compose up -d --wait` e `curl /health` com a versão do modelo esperada.
3. Painéis abrem com dados (`/dados`, `/modelos`, `/operacao`) e o MLflow mostra as execuções.
4. Uma chamada de exemplo na página de demonstração devolve setor e subgrupo.
