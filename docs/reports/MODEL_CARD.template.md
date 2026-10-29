# Model card: segmentador de chamadas

Os números deste documento vêm de `reports/metrics.json`, gerado pelo caderno. Não edite à mão: rode `make docs`.

## Uso pretendido
Classificar transcrições de call center em três setores (automotivo, home service, medicare) e agrupá-las em subgrupos dentro do setor, para análise da operação.

**Fora do escopo:** decisão sobre pessoas (atendentes ou clientes) e qualquer uso que trate os subgrupos como verdade. Eles são uma partição útil, sem gabarito humano.

## Dados
{{int:dados.chamadas}} chamadas distintas, depois de remover {{int:dados.arquivos_repetidos_removidos}} arquivos repetidos e {{int:dados.arquivos_vazios}} vazios: automotivo {{int:dados.por_setor.automotive}}, home service {{int:dados.por_setor.home_service}}, medicare {{int:dados.por_setor.medicare}}. Transcrição automática, dados pessoais já redigidos pela origem, sem separação de quem fala. {{int:setor.chamadas_desenvolvimento}} chamadas formam o desenvolvimento (treino e escolhas) e {{int:setor.chamadas_teste}} o teste, aberto uma única vez.

## Modelo
- **Setor:** TF-IDF de palavras e pares de palavras e SVM linear com calibração de probabilidade.
- **Subgrupo:** dentro do setor previsto, TF-IDF reduzido a 100 dimensões e KMeans (k = {{subgrupos.k.automotive}}, {{subgrupos.k.home_service}} e {{subgrupos.k.medicare}}), com margem para o segundo grupo.
- **Versão:** a API devolve a versão do modelo em toda resposta e em `/health`.

## Desempenho do setor
Validação cruzada de 5 dobras no desenvolvimento, agrupada por texto: F1 macro de {{pct2:setor.validacao_cruzada_referencia.f1_macro}} (desvio entre dobras de {{f3:setor.validacao_cruzada_referencia.desvio}}).

No teste ({{int:setor.chamadas_teste}} chamadas, nunca usado para escolher):

| Medida | SVM linear calibrado |
|---|---|
| F1 macro | {{pct2:setor.teste.SVM linear calibrado.F1 macro}} (IC 95%: {{pct2:setor.ic95_f1_macro.0}} a {{pct2:setor.ic95_f1_macro.1}}) |
| Chamadas erradas | {{setor.teste.SVM linear calibrado.erros}} |
| Erro de calibração (ECE) | {{f3:setor.teste.SVM linear calibrado.ECE}} |

O aviso `low_confidence` (probabilidade do setor abaixo de {{setor.limiar_baixa_confianca.escolhido}}) marcou {{pct:setor.limiar_baixa_confianca.teste.marcadas}} das chamadas de teste e capturou {{setor.limiar_baixa_confianca.teste.erros_capturados}} dos {{setor.limiar_baixa_confianca.teste.erros}} erros. O limiar foi escolhido no desenvolvimento, com orçamento de até {{pct:setor.limiar_baixa_confianca.orcamento_de_chamadas_marcadas}} das chamadas marcadas.

## Comparação de modelos
Triagem automática, validação cruzada de famílias, busca aleatória de hiperparâmetros (contra grade), medidas só com metadados, um modelo pré-treinado congelado (MiniLM) e um ajustado (DistilBERT, orçamento de CPU), combinação por voto. Tudo está no caderno, seções 4.4 a 4.13, e no painel "Modelos". No teste:

| Modelo | F1 macro | Chamadas erradas |
|---|---|---|
| SVM linear calibrado (produção) | {{pct2:setor.teste.SVM linear calibrado.F1 macro}} | {{setor.teste.SVM linear calibrado.erros}} |
| Regressão logística | {{pct2:setor.teste.regressão logística.F1 macro}} | {{setor.teste.regressão logística.erros}} |
| Melhor da busca aleatória | {{pct2:setor.teste.melhor da busca aleatória.F1 macro}} | {{setor.teste.melhor da busca aleatória.erros}} |
| Combinação de quatro modelos | {{pct2:setor.teste.combinação (pesos iguais).F1 macro}} | {{setor.teste.combinação (pesos iguais).erros}} |
| MiniLM congelado e regressão logística | {{pct2:setor.teste.MiniLM + regressão logística.F1 macro}} | {{setor.teste.MiniLM + regressão logística.erros}} |
| DistilBERT ajustado (1 época, 128 tokens) | {{pct2:setor.teste.DistilBERT com ajuste fino.F1 macro}} | {{setor.teste.DistilBERT com ajuste fino.erros}} |

A diferença entre os melhores é de poucas chamadas e não é significativa (McNemar na seção 4.13 do caderno): o setor está no teto, e a escolha entre modelos empatados seguiu a regra de simplicidade e velocidade.

## Robustez
Lendo só as primeiras palavras da chamada, o F1 macro do setor é {{pct:setor.palavras_necessarias.20}} com 20 palavras, {{pct:setor.palavras_necessarias.80}} com 80 e {{pct:setor.palavras_necessarias.320}} com 320 (chamada inteira: {{pct:setor.validacao_cruzada_referencia.f1_macro}}).

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
