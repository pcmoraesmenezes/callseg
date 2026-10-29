# Caderno de experimentação

`experimentacao.ipynb` é o registro do trabalho de ciência de dados, na ordem em que foi feito: dados, exploração, vazamento, setor, subgrupos e decisão. Foi escrito primeiro, e o código de produção (`src/call_segmenter/`) segue o que ele decidiu. Por isso o caderno é autocontido: não importa funções do pacote.

Executar: `make notebook` (leva horas na primeira vez; os passos lentos ficam em `.cache/notebook/` e as execuções seguintes levam minutos). Saídas: `reports/metrics.json`, `reports/benchmark.json` e as figuras em `reports/figures/`, que alimentam os relatórios, a apresentação e os painéis.

Para recalcular um passo lento, apague o arquivo dele em `.cache/notebook/`.

As saídas que mostravam trechos de transcrições foram omitidas, porque o dataset é de terceiros; rodar o caderno com o dataset em `data/` as reproduz.
