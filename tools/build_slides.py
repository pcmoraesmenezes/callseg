"""Gera docs/slides/apresentacao.pptx a partir de reports/metrics.json e das figuras do caderno e dos diagramas.

Nenhum número é digitado aqui: tudo sai do JSON, para a apresentação nunca divergir do caderno.
"""

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "reports" / "figures"
DIAGRAMS = ROOT / "docs" / "architecture"
OUTPUT = ROOT / "docs" / "slides" / "apresentacao.pptx"
METRICS = json.loads((ROOT / "reports" / "metrics.json").read_text())

INK, MUTED, BLUE = (RGBColor.from_string(c) for c in ("14202E", "5C6B7A", "2A6F97"))


def pct(value, digits=2):
    return f"{value * 100:.{digits}f}".replace(".", ",") + "%"


def integer(value):
    return f"{int(value):,}".replace(",", ".")


presentation = Presentation()
presentation.slide_width, presentation.slide_height = Inches(13.333), Inches(7.5)
BLANK = presentation.slide_layouts[6]


def add_text(slide, x, y, width, height, lines, size=18, color=INK, bold=False):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(width), Inches(height))
    frame = box.text_frame
    frame.word_wrap = True
    for index, line in enumerate(lines if isinstance(lines, list) else [lines]):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.space_after = Pt(8)
        run = paragraph.add_run()
        run.text = line
        run.font.size, run.font.bold, run.font.color.rgb = Pt(size), bold, color
    return box


def new_slide(title, subtitle=None):
    slide = presentation.slides.add_slide(BLANK)
    add_text(slide, 0.6, 0.4, 12.1, 0.9, title, size=28, bold=True)
    if subtitle:
        add_text(slide, 0.6, 1.2, 12.1, 0.6, subtitle, size=15, color=MUTED)
    return slide


def add_picture(slide, path, x, y, width=None, height=None):
    kwargs = {"width": Inches(width)} if width else {"height": Inches(height)}
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), **kwargs)


def add_table(slide, x, y, width, rows, column_widths, size=13, row_height=0.42):
    shape = slide.shapes.add_table(
        len(rows), len(rows[0]), Inches(x), Inches(y), Inches(width), Inches(row_height * len(rows))
    )
    for column, column_width in enumerate(column_widths):
        shape.table.columns[column].width = Inches(column_width)
    for row_number, row in enumerate(rows):
        for column, value in enumerate(row):
            cell = shape.table.cell(row_number, column)
            cell.text = str(value)
            paragraph = cell.text_frame.paragraphs[0]
            paragraph.font.size, paragraph.font.bold = Pt(size), row_number == 0
            paragraph.font.color.rgb = RGBColor(255, 255, 255) if row_number == 0 else INK
            if column > 0 and row_number > 0:
                paragraph.alignment = PP_ALIGN.RIGHT
            cell.fill.solid()
            cell.fill.fore_color.rgb = BLUE if row_number == 0 else RGBColor(0xF4, 0xF5, 0xF7)


dados, setor, subgrupos = METRICS["dados"], METRICS["setor"], METRICS["subgrupos"]
reference = setor["escolhido"]
test = setor["teste"]

slide = new_slide(
    "Segmentação de chamadas de call center", "Setor (supervisionado) e subgrupo dentro do setor (sem rótulo)"
)
add_text(
    slide,
    0.6,
    2.2,
    12,
    3,
    [
        "Entra a transcrição completa de uma chamada; saem o setor e o subgrupo.",
        f"{integer(dados['chamadas'])} chamadas distintas em três setores: automotivo, home service e medicare.",
        "Caderno de experimentação, API, pipeline de retreino com portão de promoção, painéis e decisões documentadas.",
    ],
    size=20,
)

slide = new_slide("O que há nos dados", "Parte 2 do caderno: tamanho, duração, confiança da transcrição e vocabulário")
add_picture(slide, FIGURES / "distribuicoes_por_setor.png", 0.5, 1.9, width=12.3)

slide = new_slide("Risco de vazamento: seis suspeitas, seis testes", "Parte 3 do caderno")
leak = METRICS["vazamento"]
add_table(
    slide,
    0.6,
    1.9,
    12,
    [["Teste", "F1 macro"]] + [[name, pct(value)] for name, value in leak.items()],
    [9.5, 2.5],
    size=12,
    row_height=0.4,
)

slide = new_slide(
    "Como o setor foi medido", "Desenvolvimento em validação cruzada de 5 dobras; teste aberto uma única vez"
)
add_text(
    slide,
    0.6,
    1.9,
    6,
    4.5,
    [
        f"Desenvolvimento: {integer(setor['chamadas_desenvolvimento'])} chamadas; teste: {integer(setor['chamadas_teste'])}.",
        f"Referência na validação cruzada: F1 macro {pct(setor['validacao_cruzada_referencia']['f1_macro'])}.",
        "Sobreajuste e subajuste vistos nas curvas de validação e de aprendizado.",
        "Cada chamada só aparece de um lado (grupos por texto idêntico).",
    ],
    size=17,
)
add_picture(slide, FIGURES / "curva_de_aprendizado_svm.png", 6.8, 1.9, width=6)

slide = new_slide(
    "Busca de hiperparâmetros: aleatória contra grade",
    "Mesmo orçamento de combinações; depois, a busca ampla em cinco famílias",
)
search = setor["busca_hiperparametros"]
add_table(
    slide,
    0.6,
    1.9,
    6.5,
    [
        ["Método", "Combinações", "Melhor F1", "Minutos"],
        [
            "Grade",
            search["grade"]["combinacoes"],
            pct(search["grade"]["melhor_f1"]),
            f"{search['grade']['minutos']:.1f}".replace(".", ","),
        ],
        [
            "Aleatória (mesmo orçamento)",
            search["aleatoria_mesmo_orcamento"]["combinacoes"],
            pct(search["aleatoria_mesmo_orcamento"]["melhor_f1"]),
            f"{search['aleatoria_mesmo_orcamento']['minutos']:.1f}".replace(".", ","),
        ],
    ],
    [2.8, 1.3, 1.3, 1.1],
    size=12,
)
add_picture(slide, FIGURES / "busca_grade_contra_aleatoria.png", 7.3, 1.9, width=5.7)

slide = new_slide("Modelos pré-treinados", "Embeddings congelados e ajuste fino de um BERT reduzido")
pretrained = setor["modelos_pre_treinados"]
add_text(
    slide,
    0.6,
    1.9,
    12,
    4,
    [
        f"MiniLM congelado e regressão logística, validação cruzada: F1 macro {pct(pretrained['minilm_f1_validacao_cruzada'])}.",
        f"DistilBERT ajustado (1 época, 128 tokens, CPU), primeira dobra: {pct(pretrained['distilbert_f1_primeira_dobra'])}; "
        f"o SVM na mesma dobra: {pct(pretrained['svm_f1_primeira_dobra'])}.",
        "O ajuste fino foi feito com orçamento pequeno de CPU: mede o que cabe nesse orçamento, não o teto do BERT.",
    ],
    size=18,
)

slide = new_slide("Resultado no teste", f"{integer(setor['chamadas_teste'])} chamadas nunca usadas para escolher")
rows = [["Modelo", "F1 macro", "Erros"]] + [[name, pct(row["F1 macro"]), row["erros"]] for name, row in test.items()]
add_table(slide, 0.6, 1.9, 7.2, rows, [4.4, 1.5, 1.3], size=12)
add_picture(slide, FIGURES / "matriz_de_confusao.png", 8.0, 1.9, width=5.1)
add_text(
    slide,
    0.6,
    6.4,
    12,
    0.7,
    f"{reference}: IC 95% do F1 macro de {pct(setor['ic95_f1_macro'][0])} a {pct(setor['ic95_f1_macro'][1])}.",
    size=14,
    color=MUTED,
)

slide = new_slide("O que pesa na decisão e quanto da chamada basta")
add_picture(slide, FIGURES / "termos_que_pesam.png", 0.4, 1.4, width=7.4)
add_picture(slide, FIGURES / "palavras_necessarias.png", 8.0, 1.6, width=5.0)

slide = new_slide("Subgrupos: quantos e por quê", "Silhueta, estabilidade e tamanho do menor grupo")
add_picture(slide, FIGURES / "escolha_de_k.png", 0.5, 1.9, width=12.3)

slide = new_slide("Subgrupos: o mapa e a validação por temas")
add_picture(slide, FIGURES / "mapa_umap_subgrupos.png", 0.3, 1.4, height=5.9)
add_picture(slide, FIGURES / "validacao_por_temas.png", 6.6, 1.6, width=6.5)

slide = new_slide("Arquitetura: pipeline de modelagem")
add_picture(slide, DIAGRAMS / "pipeline-de-modelagem.png", 0.4, 1.3, height=5.9)

slide = new_slide("Arquitetura: plataforma")
add_picture(slide, DIAGRAMS / "plataforma.png", 2.2, 1.2, height=6.1)

slide = new_slide("Dados em camadas e ciclo de vida do modelo")
add_picture(slide, DIAGRAMS / "dados-em-camadas.png", 0.3, 1.5, width=6.4)
add_picture(slide, DIAGRAMS / "ciclo-de-vida-do-modelo.png", 6.8, 1.5, width=6.3)

slide = new_slide("Decisões, limites e próximos passos")
add_text(
    slide,
    0.6,
    1.6,
    12,
    5.5,
    [
        "Decisões documentadas em 13 ADRs: representação, subgrupos, nomes por âncora, privacidade, estilo de arquitetura, deriva, Airflow, dados em camadas, MLflow, exposição, backend, portão de promoção e Kubernetes.",
        "Limites: subgrupos sem gabarito humano; atalho de metadados medido; modelo pré-treinado avaliado com orçamento pequeno.",
        "Próximos passos: amostra rotulada por pessoas para os subgrupos, BERT com GPU, deriva por vocabulário, rótulo de qualidade por atendente quando houver falante separado.",
    ],
    size=17,
)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
presentation.save(OUTPUT)
print("gerado", OUTPUT.relative_to(ROOT))
