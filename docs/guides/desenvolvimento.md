# Guia de desenvolvimento

## Ambiente

```bash
make install        # uv sync com os extras de desenvolvimento, caderno e MLflow
make hooks          # liga o pre-commit
make test lint
```

O projeto usa **uv**: as dependências estão em `pyproject.toml` e travadas em `uv.lock`. Para adicionar uma, `uv add <pacote>` (ou `uv add --optional notebook <pacote>` para as do caderno) e commitar os dois arquivos. A imagem Docker instala exatamente o que está no `uv.lock`.

## Como o código está organizado

| Camada | Onde | Regra |
|---|---|---|
| Modelo | `src/call_segmenter/models/` | sem web e sem banco; recebe e devolve texto e números |
| Dados | `src/call_segmenter/data/`, `text/` | leitura dos arquivos, divisão estável, pré-processamento |
| Treino | `src/call_segmenter/training/` | avaliação, portão de promoção, referência de deriva |
| Banco | `src/call_segmenter/warehouse/` | modelos ORM, migrações, ingestão, repositórios |
| Pipeline | `src/call_segmenter/pipelines/`, `cli.py` | uma função por etapa; a CLI só as chama |
| API | `backend/app/` | rotas finas, regra no serviço, banco só pelo repositório |

Pré-processamento e pós-processamento ficam em módulos com nome: `text/preprocessing.py` e `models/postprocessing.py`. O TF-IDF (minúsculas, palavras e pares de palavras, pesos) mora dentro do pipeline do classificador de setor, e o do subgrupo dentro de `SubgroupClusterer`.

## Convenções

- Nomes que se explicam (`word_count`, não `n`); funções que fazem uma coisa; tipos nas assinaturas.
- Docstring em toda função pública, com o que recebe e o que devolve quando não for óbvio.
- Teste valida comportamento (por exemplo, "o texto nunca aparece no log"), não que o framework funciona.
- Mudança de esquema do banco entra como migração (`src/call_segmenter/warehouse/migrations/versions/`); nunca como SQL solto.

## Mudar o esquema do banco

1. Edite `warehouse/models.py`.
2. Com um Postgres de teste no ar: `alembic revision --autogenerate` (a configuração está em `warehouse/migrations/env.py`), revise o arquivo gerado e commite.
3. `callseg migrate` aplica as migrações; a imagem da API roda isso antes de subir.

## Mudar os nomes dos subgrupos

Edite `src/call_segmenter/models/subgroup_names.json` (nome e termos-âncora). O treino casa cada nome ao grupo que contém suas âncoras; se algum não casar, o modelo não é promovido (ADR 0003).
