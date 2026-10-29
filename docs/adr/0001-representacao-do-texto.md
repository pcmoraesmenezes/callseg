# ADR 0001: representar o texto com TF-IDF

**Estado:** aceito.

## Contexto
Cada chamada é uma transcrição longa (mediana de mais de 500 palavras) e o dataset tem pouco mais de dez mil chamadas. Duas necessidades puxam em direções diferentes. A classificação de setor precisa ser precisa e barata de servir. Os subgrupos precisam ser **legíveis**: sem rótulo, a única forma de dar nome a um grupo é ler os termos que o definem.

## Decisão
Representar o texto com **TF-IDF de palavras e pares de palavras**. Para o setor, o vetor esparso entra direto em um classificador linear. Para os subgrupos, o TF-IDF (sem palavras comuns do inglês) é reduzido a 100 dimensões por SVD e normalizado antes do agrupamento.

## Alternativas consideradas
- **Embeddings de frase (MiniLM)**: testados no caderno, para setor e para subgrupos. Resultado e leitura no ADR 0011.
- **Modelo de linguagem com ajuste fino (DistilBERT)**: testado só para o setor, também no ADR 0011.
- **Saco de caracteres ou FastText**: não testados; o ganho esperado em texto transcrito, com erros de ortografia raros, não justificava mais uma frente.

## Consequências
- O vocabulário de cada grupo e os pesos de cada termo no classificador podem ser lidos direto. É isso que sustenta a evidência devolvida pela API (`?explain=true`) e os nomes dos subgrupos.
- A imagem da API não carrega PyTorch: só scikit-learn, o que reduz tamanho e tempo de partida.
- O modelo é sensível ao vocabulário do treino: palavras novas são ignoradas e sinônimos não se aproximam.

## Quando rever
Se o vocabulário das chamadas mudar (outro idioma, outro tipo de negócio) ou se a deriva mostrar queda de confiança sem mudança de assunto.
