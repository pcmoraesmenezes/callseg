"""Gera os diagramas de arquitetura em docs/architecture/.

Cada diagrama responde a uma pergunta:
  1. pipeline-de-modelagem  : o que acontece com uma transcrição até virarem setor e subgrupo?
  2. plataforma             : quais peças existem e como conversam?
  3. dados-em-camadas       : por onde os dados passam do arquivo ao painel?
  4. ciclo-de-vida-do-modelo: como um modelo novo entra em produção?
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "architecture"
BLUE, ORANGE, GREEN, GRAY, RED = "#2a6f97", "#e07a1f", "#5a9e6f", "#5c6b7a", "#b45309"
PALE = {BLUE: "#e8f1f7", ORANGE: "#fcefe0", GREEN: "#e7f2ea", GRAY: "#eef1f4", RED: "#fbeede"}
INK = "#14202e"


class Canvas:
    def __init__(self, width, height, title, subtitle):
        self.figure, self.axis = plt.subplots(figsize=(width, height))
        self.axis.set_xlim(0, width)
        self.axis.set_ylim(0, height)
        self.axis.axis("off")
        self.height = height
        self.axis.text(0.3, height - 0.35, title, fontsize=16, fontweight="bold", color=INK, va="top")
        self.axis.text(0.3, height - 0.85, subtitle, fontsize=10.5, color=GRAY, va="top")

    def lane(self, x, y, width, height, label, color=GRAY):
        self.axis.add_patch(
            FancyBboxPatch(
                (x, y),
                width,
                height,
                boxstyle="round,pad=0.02,rounding_size=0.15",
                fc=PALE[color],
                ec="none",
                alpha=0.55,
            )
        )
        self.axis.text(x + 0.2, y + height - 0.18, label, fontsize=9.5, fontweight="bold", color=color, va="top")

    def box(self, x, y, width, height, title, body="", color=BLUE, dashed=False):
        self.axis.add_patch(
            FancyBboxPatch(
                (x, y),
                width,
                height,
                boxstyle="round,pad=0.02,rounding_size=0.1",
                fc="white",
                ec=color,
                lw=1.8,
                ls="--" if dashed else "-",
            )
        )
        self.axis.text(
            x + width / 2, y + height - 0.14, title, ha="center", va="top", fontsize=10, fontweight="bold", color=color
        )
        if body:
            self.axis.text(
                x + width / 2,
                y + height - 0.5,
                body,
                ha="center",
                va="top",
                fontsize=8.6,
                color="#222",
                linespacing=1.4,
            )

    def arrow(self, start, end, label="", color="#444", curve=0.0, label_offset=(0, 0.12), dashed=False):
        self.axis.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                mutation_scale=14,
                lw=1.4,
                color=color,
                connectionstyle=f"arc3,rad={curve}",
                ls="--" if dashed else "-",
            )
        )
        if label:
            self.axis.text(
                (start[0] + end[0]) / 2 + label_offset[0],
                (start[1] + end[1]) / 2 + label_offset[1],
                label,
                ha="center",
                fontsize=8.2,
                color="#444",
                bbox={"fc": "white", "ec": "none", "pad": 1.5, "alpha": 0.9},
            )

    def note(self, x, y, text, color=GRAY):
        self.axis.text(x, y, text, fontsize=9, color=color, style="italic", va="top")

    def save(self, name):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        self.figure.savefig(OUTPUT / f"{name}.png", dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(self.figure)
        print("gerado", OUTPUT / f"{name}.png")


def modeling_pipeline():
    c = Canvas(
        16,
        9,
        "Pipeline de modelagem: da transcrição ao setor e ao subgrupo",
        "Leia da esquerda para a direita. Azul: classificação de setor (supervisionada). Laranja: subgrupo (não supervisionado). Cinza: entrada, saída e regras.",
    )
    c.lane(0.3, 4.9, 15.4, 2.9, "1. Inferência: uma chamada por vez", BLUE)
    c.box(0.6, 5.0, 2.2, 2.2, "Transcrição", "texto corrido da\nchamada inteira\n(sem separar quem\nfala)", GRAY)
    c.box(
        3.3,
        5.0,
        2.6,
        2.2,
        "Pré-processamento",
        "minúsculas, palavras\ne pares de palavras\npeso TF-IDF\n(vocabulário do treino)",
        BLUE,
    )
    c.box(
        6.4,
        5.0,
        2.6,
        2.2,
        "Classificador de setor",
        "SVM linear com\ncalibração: devolve a\nprobabilidade de cada\nsetor",
        BLUE,
    )
    c.box(
        9.5,
        5.0,
        2.5,
        2.2,
        "Pós-processamento",
        "setor = maior\nprobabilidade\nbaixa confiança se\nabaixo do limiar",
        BLUE,
    )
    c.box(
        12.5,
        5.0,
        3.0,
        2.2,
        "Setor",
        "automotive, home_service\nou medicare, com a\nprobabilidade e os\ntermos que pesaram",
        GRAY,
    )
    for x1, x2 in [(2.8, 3.3), (5.9, 6.4), (9.0, 9.5), (12.0, 12.5)]:
        c.arrow((x1, 6.1), (x2, 6.1))

    c.lane(0.3, 0.4, 15.4, 3.7, "2. O setor previsto escolhe qual agrupador roda", ORANGE)
    c.box(
        0.6,
        0.8,
        2.6,
        2.4,
        "Pré-processamento",
        "marcadores [TAG] viram\npalavras próprias, TF-IDF\nsem palavras comuns,\nreduzido a 100 dimensões\ne normalizado",
        ORANGE,
    )
    c.box(
        3.7,
        0.8,
        2.4,
        2.4,
        "Agrupador do setor",
        "automotive: 6 grupos\nhome_service: 8 grupos\nmedicare: 7 grupos\n(KMeans, centros\nguardados no modelo)",
        ORANGE,
    )
    c.box(
        6.6,
        0.8,
        2.6,
        2.4,
        "Pós-processamento",
        "grupo = centro mais\npróximo\nmargem sobre o 2º centro\nfrágil se estiver entre\nas 10% menores margens",
        ORANGE,
    )
    c.box(
        9.7, 0.8, 2.3, 2.4, "Nome do grupo", "casado por termos-\nâncora; sem âncora o\nmodelo não é promovido", ORANGE
    )
    c.box(
        12.5,
        0.8,
        3.0,
        2.4,
        "Resposta JSON",
        "setor, subgrupo (id, nome,\nsimilaridade, margem,\nfrágil, 2º colocado),\nbaixa confiança, avisos,\nlatência, versão do modelo",
        GRAY,
    )
    for x1, x2 in [(3.2, 3.7), (6.1, 6.6), (9.2, 9.7), (12.0, 12.5)]:
        c.arrow((x1, 2.0), (x2, 2.0))
    c.arrow((10.7, 5.0), (4.9, 3.2), "setor escolhe o agrupador", curve=-0.12, label_offset=(1.6, 0.35))
    c.arrow((14.0, 5.0), (14.0, 3.2), "setor segue na resposta", color=GRAY, label_offset=(0.9, 0))
    c.note(
        0.4,
        4.45,
        "Treino (offline, mesmo código): chamadas da camada prata -> ajusta o classificador e um agrupador por setor -> grava o modelo e a referência de deriva.",
        GRAY,
    )
    c.save("pipeline-de-modelagem")


def platform():
    c = Canvas(
        16,
        11.2,
        "Plataforma: monolito modular com tarefas em lote agendadas",
        "Estilo: requisição e resposta síncronas na API; o resto é lote agendado. Sem fila de eventos e sem microsserviços (ADR 0005). Tracejado: roda em lote.",
    )
    c.lane(0.3, 5.9, 7.2, 3.9, "Online: atende o usuário", BLUE)
    c.box(0.6, 7.2, 2.0, 1.6, "Navegador", "página estática\n(frontend/)", GRAY)
    c.box(
        3.0,
        6.3,
        4.2,
        2.5,
        "API (FastAPI)",
        "rotas -> serviço -> repositório\nmodelo vigente em memória\nmodelo candidato em sombra\n(opcional)\nmétricas Prometheus",
        BLUE,
    )
    c.arrow((2.6, 8.0), (3.0, 8.0), "HTTP")

    c.lane(7.9, 5.9, 7.8, 3.9, "Dados: um PostgreSQL, vários esquemas", GREEN)
    c.box(8.2, 8.0, 1.6, 1.3, "bronze", "arquivo como\nchegou", GREEN)
    c.box(10.0, 8.0, 1.6, 1.3, "prata", "chamada limpa,\nsem cópias", GREEN)
    c.box(11.8, 8.0, 1.6, 1.3, "ouro", "agregados e\nversões", GREEN)
    c.box(8.2, 6.2, 2.6, 1.3, "ops", "predições (só hash do texto),\nsombra, deriva", GREEN)
    c.box(12.0, 6.2, 3.4, 1.3, "Metabase", "painéis sobre ouro e ops, papel\nsó de leitura, nunca vê texto", BLUE)
    c.arrow((9.8, 8.65), (10.0, 8.65))
    c.arrow((11.6, 8.65), (11.8, 8.65))
    c.arrow((12.6, 8.0), (13.4, 7.5), "lê", color=BLUE)
    c.arrow((10.8, 6.85), (12.0, 6.85), "lê", color=BLUE)
    c.arrow((7.2, 7.0), (8.2, 6.85), "grava predições", curve=0.0, label_offset=(0, 0.3))

    c.lane(0.3, 2.9, 15.4, 2.7, "Lote: etapas do comando callseg (cada uma também roda à mão com make)", ORANGE)
    c.box(0.6, 3.2, 2.1, 1.9, "ingest", "arquivos -> bronze\n-> prata -> versão\ndos dados", ORANGE, dashed=True)
    c.box(3.0, 3.2, 2.1, 1.9, "train", "treina o candidato\nnas chamadas de\ndesenvolvimento", ORANGE, dashed=True)
    c.box(
        5.4,
        3.2,
        2.4,
        1.9,
        "promote",
        "compara com o vigente\nno teste; portão de\nlatência e de nomes",
        ORANGE,
        dashed=True,
    )
    c.box(8.1, 3.2, 2.1, 1.9, "score", "pontua a prata com\no modelo vigente", ORANGE, dashed=True)
    c.box(10.5, 3.2, 2.3, 1.9, "drift", "janela da API contra\na referência do\nmodelo; avisa", ORANGE, dashed=True)
    c.box(13.1, 3.2, 2.4, 1.9, "mlflow-log", "execuções e modelo\nregistrado", ORANGE, dashed=True)
    for x1, x2 in [(2.7, 3.0), (5.1, 5.4), (7.8, 8.1)]:
        c.arrow((x1, 4.15), (x2, 4.15))

    c.lane(0.3, 0.3, 15.4, 2.3, "Orquestração e registros", GRAY)
    c.box(0.6, 0.55, 4.0, 1.5, "Airflow", "dois DAGs: retreino semanal\ne checagem de deriva (15 min)", GRAY)
    c.box(
        5.0,
        0.55,
        5.0,
        1.5,
        "Arquivos do modelo",
        "models/segmenter.joblib (vigente), challenger.joblib\nmetadados e histórico em models/archive",
        GRAY,
    )
    c.box(10.4, 0.55, 5.1, 1.5, "MLflow", "execuções da comparação, modelo\nregistrado, figuras do caderno", GRAY)
    c.arrow((2.6, 2.05), (2.6, 3.2), "agenda", dashed=True, color=GRAY, label_offset=(0.45, 0))
    c.arrow((6.6, 3.2), (6.6, 2.05), "grava o vigente", dashed=True, color=GRAY, label_offset=(0.8, 0))
    c.arrow((14.3, 3.2), (14.3, 2.05), "registra", dashed=True, color=GRAY, label_offset=(0.5, 0))
    c.save("plataforma")


def layered_data():
    c = Canvas(
        16,
        7.6,
        "Dados em camadas: do arquivo ao painel",
        "Cada camada tem um contrato. Regra: quem lê o texto (bronze, prata) é o pipeline; o painel só lê ouro e operação.",
    )
    c.box(0.4, 2.8, 2.2, 2.6, "Arquivos", "data/<setor>/*.json\n(fora do git)\num JSON por chamada", GRAY)
    c.box(
        3.2,
        2.8,
        2.9,
        2.6,
        "Bronze",
        "bronze.raw_transcripts\no JSON como chegou\nsó acrescenta linhas\nchave: caminho + hash",
        GREEN,
    )
    c.box(
        6.7,
        2.8,
        3.1,
        2.6,
        "Prata",
        "silver.calls: uma linha por\nchamada, tipada, sem cópias\nsilver.quality_issues:\no que foi rejeitado e por quê\ndivisão desenvolvimento/teste",
        GREEN,
    )
    c.box(
        10.4,
        2.8,
        2.9,
        2.6,
        "Ouro",
        "gold.sector_profile e\nhistogramas (agregados)\ngold.dataset_versions\ngold.model_versions\ngold.holdout_confusion",
        GREEN,
    )
    c.box(13.7, 2.8, 1.9, 2.6, "Painel", "Metabase lê\nouro e ops\ncom papel\nbi_reader", BLUE)
    for x1, x2, label in [(2.6, 3.2, "ingest"), (6.1, 6.7, "valida"), (9.8, 10.4, "agrega"), (13.3, 13.7, "")]:
        c.arrow((x1, 4.1), (x2, 4.1), label)
    c.box(6.7, 0.5, 3.1, 1.6, "Treino e avaliação", "lê só a prata:\ndesenvolvimento treina,\nteste avalia", ORANGE)
    c.arrow((8.25, 2.8), (8.25, 2.1), "lê")
    c.box(10.4, 0.5, 2.9, 1.6, "ops (API)", "ops.predictions: só o hash\ndo texto, nunca o texto", BLUE)
    c.arrow((11.85, 2.1), (11.85, 2.8), "alimenta", color=BLUE)
    c.note(
        0.4,
        0.3,
        "Reexecutar é seguro: a ingestão só acrescenta o que mudou, e cada versão do conjunto de dados fica registrada.",
        GRAY,
    )
    c.save("dados-em-camadas")


def lifecycle():
    c = Canvas(
        16,
        7.8,
        "Ciclo de vida do modelo: como um modelo novo entra em produção",
        "Toda semana (ou quando houver dados novos). O modelo vigente só é trocado se o candidato passar pelo portão.",
    )
    steps = [
        (0.4, "1. Dados novos", "arquivos em data/\nentram por ingest", GRAY),
        (3.2, "2. Candidato", "train usa só o\ndesenvolvimento e grava\nmodelo + referência\nde deriva", ORANGE),
        (
            6.0,
            "3. Portão",
            "no conjunto de teste:\nnão errar mais que o\nvigente (McNemar)\nlatência no orçamento\nnomes dos grupos ok",
            ORANGE,
        ),
    ]
    for x, title, body, color in steps:
        c.box(x, 3.6, 2.5, 2.4, title, body, color)
    c.arrow((2.9, 4.8), (3.2, 4.8))
    c.arrow((5.7, 4.8), (6.0, 4.8))
    c.box(
        9.2,
        5.0,
        3.1,
        1.6,
        "4a. Promovido",
        "vira o vigente; o antigo\nvai para o histórico;\nregistro em gold.model_versions",
        GREEN,
    )
    c.box(9.2, 3.0, 3.1, 1.6, "4b. Barrado", "fica registrado como\nrejeitado, com o motivo;\no vigente continua", RED)
    c.arrow((8.5, 5.2), (9.2, 5.8), "passou")
    c.arrow((8.5, 4.4), (9.2, 3.8), "não passou (código 3)")
    c.box(
        13.0,
        4.4,
        2.6,
        2.2,
        "5. Em produção",
        "API recarrega o modelo\nscore pontua a prata\ndrift vigia a janela\nMLflow registra",
        BLUE,
    )
    c.arrow((12.3, 5.8), (13.0, 5.8))
    c.box(
        6.0,
        0.6,
        6.3,
        1.9,
        "Modo sombra (opcional, antes de promover)",
        "a API responde com o vigente e roda o candidato em segundo plano;\nops.shadow_predictions compara setor e subgrupo, e a concordância\naparece no painel de operação (callseg shadow-report).",
        GRAY,
        dashed=True,
    )
    c.arrow((7.2, 3.6), (8.0, 2.5), "opcional", dashed=True, color=GRAY)
    c.note(
        0.4,
        0.5,
        "O Airflow só agenda: cada caixa é um comando callseg que também roda à mão (make train, make promote).",
        GRAY,
    )
    c.save("ciclo-de-vida-do-modelo")


if __name__ == "__main__":
    modeling_pipeline()
    platform()
    layered_data()
    lifecycle()
