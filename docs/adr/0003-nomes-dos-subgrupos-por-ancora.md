# ADR 0003: nomes dos subgrupos casados por termos-âncora

**Estado:** aceito.

## Contexto
O KMeans devolve grupos numerados, e o número muda a cada treino. Quem usa a API precisa de nomes estáveis ("Pet: creche, reservas e conta"), e quem dá o nome é uma pessoa lendo os termos do grupo. Num retreino automático, os grupos podem ser redesenhados e o nome antigo passar a descrever outra coisa.

## Decisão
O catálogo de nomes (`subgroup_names.json`) guarda, para cada nome, **termos-âncora** (por exemplo `boarding`, `suite`). Depois de cada treino, cada nome é casado ao grupo cujo vocabulário contém mais âncoras (atribuição ótima, uma por grupo). Se algum nome ficar sem âncora, o modelo é treinado com nomes provisórios (`grupo_3`) e **o portão de promoção barra o candidato** (ADR 0014) até uma pessoa revisar o catálogo.

## Alternativas consideradas
- **Nomear pelo id do grupo**: quebra a cada retreino.
- **Gerar o nome com um modelo de linguagem a partir dos termos**: cria texto que ninguém conferiu, em um campo que aparece para o usuário.
- **Nunca retreinar**: resolve o problema de nome e cria outro, de modelo parado.

## Consequências
- O nome não depende da ordem dos grupos; o mesmo catálogo serve a modelos diferentes enquanto o desenho dos grupos for parecido.
- Retreino que muda o desenho dos grupos vira tarefa humana de revisão, com o motivo registrado em `gold.model_versions`.
- Os nomes são **hipóteses**, não verdade: não existe gabarito humano para esses grupos.
