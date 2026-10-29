# ADR 0009: dados em camadas no PostgreSQL, sem lakehouse

**Estado:** aceito.

## Contexto
Os dados chegam como arquivos JSON (dezenas de milhares ao longo do tempo, centenas de megabytes), precisam de limpeza com regras explícitas, de versão (qual conjunto treinou qual modelo) e de agregados para painéis.

## Decisão
Arquitetura em camadas (medalhão) dentro de um único PostgreSQL, com um esquema por camada e DDL versionada em migrações Alembic:
- **bronze**: o arquivo como chegou; só acrescenta linhas; chave é caminho mais hash do conteúdo, então reingerir é seguro.
- **prata**: uma linha por chamada, tipada e sem cópias, com a divisão desenvolvimento/teste decidida por hash do texto (uma chamada nunca troca de lado quando o conjunto cresce); `quality_issues` registra o que foi rejeitado e por quê.
- **ouro**: agregados para painel, versões do conjunto de dados e dos modelos, matriz de confusão do teste.
- **ops**: o que a API gera (predições, modo sombra, deriva).

## Alternativas consideradas
- **Lakehouse (arquivos em armazenamento de objetos, formato Delta ou Iceberg, motor Spark ou DuckDB)**: resolve volumes de terabytes e dados semiestruturados heterogêneos. Aqui são centenas de megabytes de JSON de um único formato, e um PostgreSQL já dá transação, esquema, índice e SQL para o Metabase.
- **Só arquivos mais DVC**: o dataset é de terceiros e não pode ter remoto; a versão fica como hash em `gold.dataset_versions`.
- **Dado cru só em arquivos, sem bronze**: perderia o registro do que foi ingerido e quando.

## Consequências
- Uma tecnologia só para dado, painel e metadados do orquestrador (bancos separados no mesmo servidor).
- O bronze guarda texto de terceiros: só existe onde o pipeline roda sobre o dataset, nunca na demonstração pública (ADR 0004).

## Quando rever
Se o volume passar de dezenas de gigabytes, se chegarem fontes de formatos diferentes ou se o painel precisar de consultas que o PostgreSQL não sustente.
