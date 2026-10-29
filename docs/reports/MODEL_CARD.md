# Model card: segmentador de chamadas

Os números deste documento vêm de `reports/metrics.json`, gerado pelo caderno. Não edite à mão: rode `make docs`.

## Uso pretendido
Classificar transcrições de call center em três setores (automotivo, home service, medicare) e agrupá-las em subgrupos dentro do setor, para análise da operação.

**Fora do escopo:** decisão sobre pessoas (atendentes ou clientes) e qualquer uso que trate os subgrupos como verdade. Eles são uma partição útil, sem gabarito humano.

## Dados
10.121 chamadas distintas, depois de remover 167 arquivos repetidos e 2 vazios: automotivo 2.811, home service 4.196, medicare 3.114. Transcrição automática, dados pessoais já redigidos pela origem, sem separação de quem fala. 8.094 chamadas formam o desenvolvimento (treino e escolhas) e 2.027 o teste, aberto uma única vez.

## Modelo
- **Setor:** TF-IDF de palavras e pares de palavras e SVM linear com calibração de probabilidade.
- **Subgrupo:** dentro do setor previsto, TF-IDF reduzido a 100 dimensões e KMeans (k = 6, 8 e 7), com margem para o segundo grupo.
- **Versão:** a API devolve a versão do modelo em toda resposta e em `/health`.

## Desempenho do setor
Validação cruzada de 5 dobras no desenvolvimento, agrupada por texto: F1 macro de 99,35% (desvio entre dobras de 0,001).

No teste (2.027 chamadas, nunca usado para escolher):

| Medida | SVM linear calibrado |
|---|---|
| F1 macro | 99,21% (IC 95%: 98,83% a 99,56%) |
| Chamadas erradas | 16 |
| Erro de calibração (ECE) | 0,007 |

O aviso `low_confidence` (probabilidade do setor abaixo de 0,9) marcou 3,7% das chamadas de teste e capturou 12 dos 16 erros. O limiar foi escolhido no desenvolvimento, com orçamento de até 6,0% das chamadas marcadas.

## Comparação de modelos
Triagem automática, validação cruzada de famílias, busca aleatória de hiperparâmetros (contra grade), medidas só com metadados, um modelo pré-treinado congelado (MiniLM) e um ajustado (DistilBERT, orçamento de CPU), combinação por voto. Tudo está no caderno, seções 4.4 a 4.13, e no painel "Modelos". No teste:

| Modelo | F1 macro | Chamadas erradas |
|---|---|---|
| SVM linear calibrado (produção) | 99,21% | 16 |
| Regressão logística | 99,15% | 17 |
| Melhor da busca aleatória | 99,31% | 14 |
| Combinação de quatro modelos | 99,15% | 17 |
| MiniLM congelado e regressão logística | 97,66% | 47 |
| DistilBERT ajustado (1 época, 128 tokens) | 96,43% | 68 |

A diferença entre os melhores é de poucas chamadas e não é significativa (McNemar na seção 4.13 do caderno): o setor está no teto, e a escolha entre modelos empatados seguiu a regra de simplicidade e velocidade.

## Robustez
Lendo só as primeiras palavras da chamada, o F1 macro do setor é 86,1% com 20 palavras, 96,3% com 80 e 99,0% com 320 (chamada inteira: 99,4%).

## Subgrupos
Sem gabarito, a validação é por estabilidade, vizinhança e concordância com temas independentes (caderno, seção 5). Cada nome de grupo carrega termos-âncora; o treino falha em promover o modelo se o vocabulário do grupo deixar de contê-los.

## Limitações conhecidas
- Subgrupos são hipóteses sem gabarito humano; grupos de conversa genérica (URA, aviso de gravação) não têm tema dominante.
- Existe um atalho de metadados (a confiança da transcrição e a duração separam parte dos setores sem ler o texto); o desempenho do modelo vem do texto, mas o atalho é um risco se a origem das transcrições mudar.
- Erro de setor propaga para o subgrupo.
- O modelo pré-treinado foi avaliado com orçamento pequeno de CPU: não representa o teto de modelos de linguagem.

## Monitoramento
`callseg drift` compara a janela recente da API com a referência fora da amostra gravada junto do modelo: taxa de baixa confiança, atribuição frágil, mistura de setores e confiança média (ADR 0006).

## Privacidade
O texto da chamada nunca é gravado nem registrado em log: o banco guarda o resumo da predição e o hash do texto. O painel de BI lê por um papel que só tem `SELECT` em agregados.
