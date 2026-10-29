# ADR 0011: embeddings de frase e BERT não entram no setor

**Estado:** aceito, com a ressalva do orçamento de computação.

## Contexto
O TF-IDF só enxerga as palavras presentes. Modelos de linguagem treinados em bilhões de palavras leem contexto e tratam sinônimos, e a pergunta natural é por que um BERT não foi testado.

## O que foi feito
Dois testes no caderno (parte 4.8), com o mesmo critério de validação:
1. **Embeddings congelados.** O `all-MiniLM-L6-v2` transforma trechos de 180 palavras em vetores, a chamada vira a média, e uma regressão logística aprende o setor.
2. **Ajuste fino.** O `distilbert-base-uncased` foi treinado nas chamadas, 1 época, lendo os primeiros 128 tokens, na primeira dobra. A máquina não tem GPU: uma tentativa maior (2 épocas, 256 tokens) passou de uma hora sem terminar e foi interrompida.

## Resultado
| Modelo | F1 macro |
|---|---|
| TF-IDF e SVM (referência) | 0,9908 na primeira dobra; 0,9935 na validação cruzada |
| MiniLM congelado e regressão logística | 0,9720 na validação cruzada |
| DistilBERT ajustado (orçamento pequeno) | 0,9475 na primeira dobra |

No teste, os dois ficam estatisticamente abaixo do SVM (McNemar, p < 0,001).

Para os subgrupos, os embeddings dão partições bem diferentes das do TF-IDF (ARI entre 0,17 e 0,28) e são mais estáveis em dois dos três setores. Sem gabarito, isso não decide qual está certa.

## Decisão
Manter o TF-IDF no setor e nos subgrupos. Os embeddings seguem como linha de pesquisa para os subgrupos (um modelo híbrido para o automotivo).

## Consequências
- A imagem da API não carrega PyTorch.
- A conclusão vale **para este orçamento**: não prova que um BERT com GPU, a chamada inteira em trechos e mais épocas perderia. É o primeiro candidato se um dia houver GPU.
