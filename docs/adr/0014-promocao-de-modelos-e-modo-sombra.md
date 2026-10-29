# ADR 0014: promoção de modelos por portão e modo sombra

**Estado:** aceito.

## Contexto
Com retreino automático, um modelo pior pode chegar à produção sem ninguém ver. O conjunto de teste precisa ser o mesmo entre versões, senão as comparações não valem.

## Decisão
- A divisão entre desenvolvimento e teste sai do **hash do texto** da chamada, então o teste só cresce, nunca embaralha, e o modelo é treinado só com o desenvolvimento.
- O candidato é comparado ao vigente no teste (McNemar sobre as chamadas em que discordam). O portão **barra regressão**: erro significativamente maior (p < 0,05), latência mediana acima do orçamento (50 ms) ou grupos que não casam com os nomes do catálogo. Empate promove, porque o candidato costuma ter mais dados.
- O resultado (promovido ou rejeitado, com motivo) fica em `gold.model_versions`; o vigente anterior vai para `models/archive`.
- **Modo sombra:** com `SHADOW_MODEL_PATH`, a API responde com o vigente e, em segundo plano, roda o candidato e grava a resposta dele (`ops.shadow_predictions`). O painel de operação mostra a concordância de setor e de subgrupo. Serve para ver o candidato em tráfego real antes de promover.

## Alternativas consideradas
- **Promover sempre**: rápido e perigoso.
- **Exigir melhora estatística**: com setor perto do teto, quase nenhum candidato mostraria melhora, e o modelo ficaria parado enquanto os dados mudam.
- **Teste A/B com usuários**: o usuário da API não vê diferença de interface; o modo sombra responde à mesma pergunta sem afetar ninguém.

## Consequências
Um retreino que redesenhe os grupos exige revisão humana dos nomes (ADR 0003). O portão não mede qualidade dos subgrupos além dos nomes; isso é limitação conhecida.
