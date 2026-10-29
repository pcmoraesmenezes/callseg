# ADR 0006: como detectar deriva

**Estado:** aceito.

## Contexto
Sem rótulo em produção, não dá para medir acerto. O que se observa são sinais indiretos da distribuição das respostas.

## Decisão
Comparar a janela recente de predições da API com uma **referência fora da amostra**, medida por validação cruzada no treino e gravada junto do modelo (`models/segmenter.meta.json`). Quatro sinais:
1. taxa de chamadas em baixa confiança (teste z, alerta acima de 3 desvios);
2. taxa de atribuição frágil do subgrupo (teste z);
3. mistura de setores (PSI, alerta acima de 0,2);
4. queda da confiança média do setor (mais de 5 pontos percentuais).
Janela com menos de 30 chamadas não decide. O resultado de cada checagem vai para `ops.drift_checks` e, havendo alerta, para o Telegram.

## Alternativas consideradas
- **Referência no próprio treino**: a confiança nas chamadas que o modelo viu é otimista e geraria alarme falso permanente.
- **Teste de distribuição sobre o texto (por exemplo, divergência de vocabulário)**: mais sensível, mas caro e difícil de explicar a quem recebe o alerta.
- **Medir acerto com amostra rotulada por pessoas**: o melhor sinal, mas depende de gente; entra como evolução.

## Consequências
Em um teste com tráfego de chamadas truncadas a 40 palavras, o sinal que mais reagiu foi a taxa de baixa confiança; a taxa de atribuição frágil quase não se moveu. Por isso o painel destaca a baixa confiança como sinal principal.
