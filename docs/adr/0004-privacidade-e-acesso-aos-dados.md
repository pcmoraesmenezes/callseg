# ADR 0004: privacidade e acesso aos dados

**Estado:** aceito.

## Contexto
O dataset é de terceiros, com dados pessoais já redigidos pela origem (marcadores como `[PERSON_NAME]`). A API recebe texto de quem a usa, e os painéis são públicos na demonstração.

## Decisão
- O **texto da chamada nunca é gravado nem registrado em log** pela API. O banco guarda o resumo da predição e o hash SHA-256 do texto.
- O texto bruto só existe nas camadas bronze e prata, lidas apenas pelo pipeline. O dataset não é copiado para o servidor da demonstração; lá entram só o modelo, as predições e os agregados da camada ouro.
- O Metabase lê por um papel de banco (`bi_reader`) com `SELECT` só em ouro e operação. Ele não enxerga bronze nem prata.
- O dataset, os modelos treinados e o `.env` ficam fora do git, o que o CI confere.

## Alternativas consideradas
- Guardar o texto para facilitar auditoria: rejeitado, porque o ganho (reproduzir uma resposta) não compensa guardar dado de terceiros e de visitantes.
- Anonimizar de novo na entrada: a origem já fez; refazer sem rótulo confiável criaria falsos positivos.

## Consequências
- Reproduzir uma resposta exige reenviar o texto; o hash permite apenas conferir que é o mesmo texto.
- A camada ouro precisa ser construída só com agregados; um teste de revisão confere que nenhuma tabela de ouro tem coluna de texto.
