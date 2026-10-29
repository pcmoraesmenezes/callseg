# ADR 0010: MLflow para rastreio e registro

**Estado:** aceito.

## Contexto
A comparação de modelos gera dezenas de execuções (triagem, validação cruzada, busca de hiperparâmetros, teste) e o modelo vigente precisa de um registro com versão, parâmetros e artefatos.

## Decisão
Servidor MLflow com metadados no PostgreSQL e artefatos em volume, atrás de proxy com senha. `callseg mlflow-log` registra uma execução por candidato avaliado no caderno (a etapa vai como tag) e o modelo vigente como `pyfunc`, com a marca de experimento de treino de modelo para que a interface abra na visão de execuções.

## Alternativas consideradas
- **Só `gold.model_versions`**: guarda estado e motivo da promoção, mas não compara execuções nem guarda figuras. Os dois convivem: o banco é a fonte do que está em produção, o MLflow é o laboratório.
- **Weights & Biases e similares**: serviço de terceiros, sem necessidade aqui.

## Consequências
O MLflow não tem login próprio, e quem entra pode apagar execuções: só o proxy publica porta (ADR 0012).
