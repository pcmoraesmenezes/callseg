# ADR 0005: monolito modular com tarefas em lote, sem microsserviços nem fila de eventos

**Estado:** aceito.

## Contexto
O problema tem duas partes de natureza diferente: **responder** a uma chamada em milissegundos (online) e **manter o modelo** em dia com dados novos (lote, semanal). A carga é pequena (uma chamada leva poucos milissegundos para segmentar (mediana de cerca de 4 ms em máquina ociosa)), há um único modelo em produção e a equipe é uma pessoa.

## Decisão
- **Online:** uma API FastAPI, síncrona (requisição e resposta), em um único processo, com o modelo em memória. Por dentro é modular: rotas, serviço, repositório e modelos de banco em camadas separadas (ADR 0013).
- **Lote:** etapas do comando `callseg` (ingest, train, promote, score, drift), agendadas pelo Airflow (ADR 0008). Cada etapa também roda à mão.
- **Estado:** um PostgreSQL com esquemas por camada (ADR 0009).
- Sem fila de eventos, sem comunicação assíncrona entre serviços, sem serviços separados por função.

## Alternativas consideradas
- **Microsserviços** (um para setor, um para subgrupo): a segmentação em dois estágios leva alguns milissegundos; separar em rede acrescentaria latência, pontos de falha e versões a coordenar sem ganho de escala, porque os dois modelos escalam juntos.
- **Orientado a eventos** (fila entre ingestão, treino e API): faria sentido com milhares de chamadas por minuto ou vários consumidores do mesmo fluxo. Aqui o fluxo é um lote semanal e uma API; o banco já é o ponto de encontro.
- **Serverless**: o modelo carrega em dezenas de segundos e pesa dezenas de megabytes; a partida fria anularia a vantagem.
- **Kubernetes**: ADR 0015.

## Consequências
- Poucas peças para operar, depurar e explicar; o fluxo de dados cabe em um diagrama (`docs/architecture/plataforma.png`).
- A API e o pipeline de lote compartilham o mesmo pacote Python, então não existe duas versões da lógica de segmentação.
- Escalar a API é subir mais réplicas atrás de um balanceador (o modelo é somente leitura). O gargalo seguinte seria o banco de predições, não a API.

## Quando rever
Se aparecer um segundo produto que consuma as segmentações, ou volume que exija processar em fila, ou mais de um modelo em produção por setor.
