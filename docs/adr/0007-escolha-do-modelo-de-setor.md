# ADR 0007: SVM linear calibrado para o setor

**Estado:** aceito.

## Contexto
O setor é um problema com três classes quase equilibradas e texto longo. Um TF-IDF com regressão logística sem ajuste já passa de 0,99 de F1 macro na validação cruzada, então a disputa entre modelos é de poucas dezenas de chamadas em mais de dez mil. A decisão precisava de método, para não escolher o vencedor de uma busca que apenas teve sorte.

## Decisão
Modelo de produção: **TF-IDF de palavras e pares de palavras e SVM linear com calibração de probabilidade** (`CalibratedClassifierCV` sobre `LinearSVC`).

Método da escolha (caderno, parte 4):
- 20% das chamadas ficam como teste, separadas antes de qualquer escolha, com chamadas de texto idêntico sempre do mesmo lado.
- Toda comparação usa validação cruzada de 5 dobras estratificada e agrupada, só no desenvolvimento.
- Regra fixada antes de abrir o teste: vence o maior F1 médio; se a diferença para um modelo mais simples e rápido for menor que o desvio entre dobras, fica o mais simples.

## Alternativas consideradas e o que se mediu
| Alternativa | Resultado | Leitura |
|---|---|---|
| Triagem automática (26 classificadores) | lineares no topo, árvores abaixo, vizinhos mais próximos muito abaixo | nenhuma família óbvia ficou de fora |
| Ridge e SVM linear | empatam no topo na validação cruzada | escolhido o SVM por dar probabilidade calibrada e ser tão simples quanto |
| Regressão logística | um pouco abaixo na validação, pior calibrada | ECE de 0,05 contra 0,0065 do SVM calibrado no teste |
| Busca aleatória, 40 combinações em cinco famílias | melhor (Ridge) empata com o SVM no teste, p = 0,50 | não compensa o custo de trigramas |
| Grade contra busca aleatória, com o mesmo orçamento | a grade foi um pouco melhor num espaço pequeno e bem desenhado | a busca aleatória se justifica quando o espaço é grande |
| Metadados somados ao texto | validação sobe de 0,9935 para 0,9962 | descartado: o ganho vem de um atalho de origem do áudio (ADR 0004 e caderno, seção 4.7) |
| Combinação por voto de quatro modelos | não supera o SVM sozinho | os modelos erram nas mesmas chamadas |
| Três detectores binários | equivale ao multiclasse (o `LinearSVC` já é um-contra-todos) | o sinal "nenhum ou vários positivos" é útil como dúvida |
| Modelos pré-treinados | abaixo do TF-IDF | ADR 0011 |

## Consequências
- Poucos erros por setor (cerca de 0,7%), e o aviso de baixa confiança em 0,90 captura a maior parte deles (ADR 0006 e caderno, seção 4.14).
- O treino leva segundos e o modelo pesa dezenas de megabytes.
- Diferenças abaixo de 0,001 de F1 não são distinguíveis com este tamanho de teste: qualquer afirmação de "melhor" entre os finalistas é de empate.

## Quando rever
Se o teste crescer o bastante para separar os finalistas, se os dados mudarem de domínio, ou se a deriva mostrar queda de confiança sustentada.
