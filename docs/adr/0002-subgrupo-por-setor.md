# ADR 0002: agrupar chamadas dentro de cada setor

**Estado:** aceito.

## Contexto
O produto precisa de uma segunda segmentação, "dentro do setor previsto", sem rótulo. A exploração mostrou que cada setor mistura negócios diferentes (medicare traz consultório e serviços para animais; home service traz vidro, fauna e pesquisa de satisfação).

## Decisão
Primeiro classificar o setor; depois rodar **um agrupador por setor**, treinado só com as chamadas daquele setor. Algoritmo: KMeans sobre TF-IDF reduzido (ADR 0001), com k = 6 (automotive), 8 (home_service) e 7 (medicare). A escolha de k combinou silhueta, estabilidade entre amostras e tamanho do menor grupo; os números estão na seção 5.2 do caderno.

## Alternativas consideradas
- **Um agrupamento global**: acabaria redescobrindo os setores e deixaria pouca resolução para o que existe dentro deles.
- **Mistura de gaussianas, hierárquico, NMF e DBSCAN**: comparados no caderno (seção 5.3). O DBSCAN deixa muitas chamadas como ruído; os demais concordam parcialmente com o KMeans. Nenhum venceu com folga em estabilidade, então ficou o mais simples e que atribui chamadas novas por distância a centros.
- **Modelos de tópicos (LDA)**: não testados; NMF cobre a mesma ideia.

## Consequências
- Um erro de setor propaga para o subgrupo (a chamada é comparada aos grupos do setor errado).
- Cada resposta traz a **margem** para o segundo grupo mais próximo e marca como frágil a atribuição com margem entre as 10% menores do treino.
- k é fixo: se o negócio ganhar um tipo novo de chamada, ele cai no grupo mais próximo até o retreino.

## Quando rever
Quando a taxa de atribuição frágil subir de forma sustentada (sinal de deriva, ADR 0006).
