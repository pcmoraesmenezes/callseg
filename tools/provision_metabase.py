"""Cria (ou atualiza) no Metabase a fonte de dados, as perguntas, os três painéis e a página inicial.

É idempotente: perguntas e painéis são encontrados pelo nome e atualizados, então rodar de novo só aplica o que mudou.
Os painéis ficam com link público e a página inicial (`/`) e os atalhos (`/dados`, `/modelos`, `/operacao`) são
gravados em `HUB_DIR`, que o proxy do BI serve. Os painéis abrem em tema escuro.

Variáveis: METABASE_URL, POSTGRES_DB, BI_PASSWORD, METABASE_ADMIN_EMAIL, METABASE_ADMIN_PASSWORD, HUB_DIR.
"""

import html
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BLUE, ORANGE, GREEN, RED = "#2a6f97", "#e07a1f", "#5a9e6f", "#c0392b"
DARK_THEME = "#theme=night&titled=true"


def sql(query: str) -> str:
    return " ".join(query.split())


def bars(dimension, metric, color, low=None, values=False):
    settings = {
        "graph.dimensions": [dimension],
        "graph.metrics": [metric],
        "graph.max_categories_enabled": True,
        "graph.max_categories": 40,
        "series_settings": {metric: {"color": color}},
    }
    if low is not None:
        settings.update({"graph.y_axis.auto_range": False, "graph.y_axis.min": low, "graph.y_axis.max": 100})
    if values:
        settings["graph.show_values"] = True
    return settings


def stacked(dimension, series, metric):
    return {
        "graph.dimensions": [dimension, series],
        "graph.metrics": [metric],
        "stackable.stack_type": "stacked",
        "series_settings": {
            "automotive": {"color": BLUE},
            "home_service": {"color": ORANGE},
            "medicare": {"color": GREEN},
        },
    }


def text(markdown: str, position):
    return {"text": markdown, "pos": position}


DATA_DASHBOARD = "Dados: o que há nas transcrições"
MODEL_DASHBOARD = "Modelos: qual classifica melhor o setor"
OPERATION_DASHBOARD = "Operação: a API em uso"

DATA_CARDS = [
    text(
        "**Quem são as chamadas.** Os números vêm da camada de ouro do banco: agregados calculados a partir das "
        "chamadas já limpas. Nenhum texto de chamada chega a este painel.",
        (0, 0, 24, 2),
    ),
    {
        "name": "Chamadas distintas",
        "display": "scalar",
        "pos": (0, 2, 6, 3),
        "sql": "SELECT sum(calls) FROM gold.sector_profile",
    },
    {
        "name": "Mediana de palavras por chamada",
        "display": "scalar",
        "pos": (6, 2, 6, 3),
        "sql": "SELECT round(percentile_cont(0.5) WITHIN GROUP (ORDER BY words_p50)::numeric) FROM gold.sector_profile",
    },
    {
        "name": "Confiança da transcrição (média das medianas dos setores)",
        "display": "scalar",
        "pos": (12, 2, 6, 3),
        "sql": "SELECT round(avg(confidence_p50)::numeric, 3) FROM gold.sector_profile",
    },
    {
        "name": "Versões do conjunto de dados",
        "display": "scalar",
        "pos": (18, 2, 6, 3),
        "sql": "SELECT count(*) FROM gold.dataset_versions",
    },
    {
        "name": "Chamadas por setor",
        "display": "bar",
        "pos": (0, 5, 8, 7),
        "sql": 'SELECT sector AS "Setor", calls AS "Chamadas" FROM gold.sector_profile ORDER BY calls DESC',
        "settings": bars("Setor", "Chamadas", BLUE, values=True),
    },
    {
        "name": "Perfil de cada setor",
        "display": "table",
        "pos": (8, 5, 16, 7),
        "sql": """SELECT sector AS "Setor", calls AS "Chamadas", words_p05 AS "Palavras (5%)", words_p50 AS "Palavras (mediana)",
                  words_p95 AS "Palavras (95%)", duration_p50 AS "Duração mediana (s)",
                  round(confidence_p50::numeric, 3) AS "Confiança mediana" FROM gold.sector_profile ORDER BY sector""",
    },
    {
        "name": "Distribuição de palavras por chamada",
        "display": "bar",
        "pos": (0, 12, 12, 8),
        "sql": """SELECT bin_start AS "Faixa de palavras (início)", sector AS "Setor", calls AS "Chamadas"
                  FROM gold.size_histogram WHERE measure = 'words' ORDER BY 1""",
        "settings": stacked("Faixa de palavras (início)", "Setor", "Chamadas"),
    },
    {
        "name": "Distribuição da confiança da transcrição",
        "display": "bar",
        "pos": (12, 12, 12, 8),
        "sql": """SELECT bin_start AS "Confiança (início da faixa)", sector AS "Setor", calls AS "Chamadas"
                  FROM gold.size_histogram WHERE measure = 'asr_confidence' ORDER BY 1""",
        "settings": stacked("Confiança (início da faixa)", "Setor", "Chamadas"),
    },
    text(
        "**Leitura.** O automotivo tem as chamadas mais longas e a transcrição mais confiável; o home service é o "
        "maior setor e o de chamadas mais curtas. A diferença de confiança entre setores é um atalho possível para o "
        "modelo, medido e descartado como explicação no caderno (seção 3).",
        (0, 20, 24, 2),
    ),
]

SUBGROUP_CARDS = [
    {
        "name": f"Subgrupos de {sector}",
        "display": "row",
        "pos": (0, 22 + index * 6, 24, 6),
        "sql": f"""SELECT subgroup_name AS "Subgrupo", calls AS "Chamadas" FROM gold.v_subgroup_mix
                   WHERE source = 'dataset' AND sector = '{sector}' ORDER BY calls DESC""",
        "settings": bars("Subgrupo", "Chamadas", color),
    }
    for index, (sector, color) in enumerate([("automotive", BLUE), ("home_service", ORANGE), ("medicare", GREEN)])
]

MODEL_CARDS = [
    text(
        "**Pergunta:** qual modelo classifica melhor o setor? Toda escolha usa só o conjunto de desenvolvimento, em "
        "validação cruzada de 5 dobras agrupada por chamada. O conjunto de teste foi aberto uma vez.",
        (0, 0, 24, 2),
    ),
    {
        "name": "Triagem automática: F1 macro dos 12 melhores",
        "display": "row",
        "pos": (0, 2, 12, 10),
        "sql": """SELECT model AS "Modelo", round(f1_macro::numeric * 100, 2) AS "F1 macro (%)" FROM ops.model_benchmark
                  WHERE stage = 'triagem' ORDER BY f1_macro DESC LIMIT 12""",
        "settings": bars("Modelo", "F1 macro (%)", BLUE, low=95, values=True),
    },
    {
        "name": "Validação cruzada: famílias de modelo sobre TF-IDF",
        "display": "row",
        "pos": (12, 2, 12, 10),
        "sql": """SELECT model AS "Modelo", round(f1_macro::numeric * 100, 2) AS "F1 macro (%)" FROM ops.model_benchmark
                  WHERE stage = 'validacao_cruzada' ORDER BY f1_macro DESC""",
        "settings": bars("Modelo", "F1 macro (%)", GREEN, low=97, values=True),
    },
    {
        "name": "Busca aleatória: melhor F1 macro por família",
        "display": "row",
        "pos": (0, 12, 12, 8),
        "sql": """SELECT model AS "Família", round(max(f1_macro)::numeric * 100, 2) AS "F1 macro (%)" FROM ops.model_benchmark
                  WHERE stage = 'busca_aleatoria' GROUP BY model ORDER BY 2 DESC""",
        "settings": bars("Família", "F1 macro (%)", ORANGE, low=97, values=True),
    },
    {
        "name": "Busca aleatória: cada combinação testada",
        "display": "scatter",
        "pos": (12, 12, 12, 8),
        "sql": """SELECT trial AS "Combinação sorteada", model AS "Família", round(f1_macro::numeric * 100, 2) AS "F1 macro (%)"
                  FROM ops.model_benchmark WHERE stage = 'busca_aleatoria'""",
        "settings": {"graph.dimensions": ["Combinação sorteada", "Família"], "graph.metrics": ["F1 macro (%)"]},
    },
    {
        "name": "Teste final: chamadas que nenhum modelo viu na escolha",
        "display": "table",
        "pos": (0, 20, 14, 8),
        "sql": """SELECT model AS "Modelo", round(f1_macro::numeric * 100, 2) AS "F1 macro (%)", errors AS "Chamadas erradas",
                  round(accuracy::numeric * 100, 2) AS "Acurácia (%)", round(ece::numeric, 4) AS "Erro de calibração"
                  FROM ops.model_benchmark WHERE stage = 'teste' ORDER BY f1_macro DESC""",
    },
    {
        "name": "Matriz de confusão do modelo vigente (chamadas de teste)",
        "display": "table",
        "pos": (14, 20, 10, 8),
        "sql": """SELECT true_sector AS "Setor real", predicted_sector AS "Previsto como", calls AS "Chamadas"
                  FROM gold.holdout_confusion WHERE model_version = (
                      SELECT model_version FROM gold.model_versions WHERE status = 'champion' LIMIT 1)
                  ORDER BY (true_sector = predicted_sector) DESC, calls DESC""",
    },
]

SUBGROUP_MODEL_CARDS = [
    text(
        "**Subgrupos: o que as análises do caderno mostram.** Sem gabarito, a validação é por estabilidade (o mesmo "
        "agrupamento reaparece com outra amostra?), vizinhança (os vizinhos mais próximos caem no mesmo grupo?) e "
        "comparação de algoritmos e de representações. O mapa em duas dimensões (UMAP) está no caderno, seção 5.4.",
        (0, 28, 24, 2),
    ),
    {
        "name": "Escolha de k: estabilidade por número de grupos",
        "display": "line",
        "pos": (0, 30, 12, 8),
        "sql": """SELECT label::int AS "k", sector AS "Setor", round(value::numeric, 2) AS "Estabilidade"
                  FROM gold.subgroup_analysis WHERE analysis = 'escolha_de_k' AND metric = 'estabilidade' ORDER BY 1""",
        "settings": {
            "graph.dimensions": ["k", "Setor"],
            "graph.metrics": ["Estabilidade"],
            "series_settings": {
                "automotive": {"color": BLUE},
                "home_service": {"color": ORANGE},
                "medicare": {"color": GREEN},
            },
        },
    },
    {
        "name": "Algoritmos de agrupamento: estabilidade em amostras diferentes",
        "display": "bar",
        "pos": (12, 30, 12, 8),
        "sql": """SELECT label AS "Algoritmo", sector AS "Setor", round(value::numeric, 3) AS "Estabilidade"
                  FROM gold.subgroup_analysis WHERE analysis = 'algoritmos' AND metric = 'estabilidade' ORDER BY 1""",
        "settings": {
            "graph.dimensions": ["Algoritmo", "Setor"],
            "graph.metrics": ["Estabilidade"],
            "series_settings": {
                "automotive": {"color": BLUE},
                "home_service": {"color": ORANGE},
                "medicare": {"color": GREEN},
            },
        },
    },
    {
        "name": "DBSCAN contra os demais: % de chamadas tratadas como ruído",
        "display": "bar",
        "pos": (0, 38, 12, 8),
        "sql": """SELECT label AS "Algoritmo", sector AS "Setor", round(value::numeric * 100, 1) AS "% como ruído"
                  FROM gold.subgroup_analysis WHERE analysis = 'algoritmos' AND metric = 'ruido' ORDER BY 1""",
        "settings": {
            "graph.dimensions": ["Algoritmo", "Setor"],
            "graph.metrics": ["% como ruído"],
            "series_settings": {
                "automotive": {"color": BLUE},
                "home_service": {"color": ORANGE},
                "medicare": {"color": GREEN},
            },
        },
    },
    {
        "name": "Vizinhança: pureza dos 10 vizinhos mais próximos",
        "display": "table",
        "pos": (12, 38, 12, 8),
        "sql": """SELECT sector AS "Setor",
                         round(max(value) FILTER (WHERE metric = 'pureza_media')::numeric, 3) AS "Pureza média",
                         round(max(value) FILTER (WHERE metric = 'pureza_do_grupo_mais_fraco')::numeric, 3) AS "Grupo mais fraco",
                         round(max(value) FILTER (WHERE metric = 'teste_centro_e_vizinhos_concordam')::numeric, 3) AS "Teste: centro e vizinhos concordam"
                  FROM gold.subgroup_analysis WHERE analysis = 'vizinhanca' GROUP BY sector ORDER BY sector""",
    },
    {
        "name": "Embeddings contra TF-IDF: estabilidade",
        "display": "bar",
        "pos": (0, 46, 12, 8),
        "sql": """SELECT sector AS "Setor", 'TF-IDF' AS "Representação", round(value::numeric, 3) AS "Estabilidade"
                  FROM gold.subgroup_analysis WHERE analysis = 'embeddings' AND metric = 'estabilidade_tfidf'
                  UNION ALL
                  SELECT sector, 'Embedding (MiniLM)', round(value::numeric, 3)
                  FROM gold.subgroup_analysis WHERE analysis = 'embeddings' AND metric = 'estabilidade_embedding' ORDER BY 1, 2""",
        "settings": {
            "graph.dimensions": ["Setor", "Representação"],
            "graph.metrics": ["Estabilidade"],
            "series_settings": {"TF-IDF": {"color": BLUE}, "Embedding (MiniLM)": {"color": ORANGE}},
        },
    },
    {
        "name": "Embeddings contra TF-IDF: o quanto concordam",
        "display": "table",
        "pos": (12, 46, 12, 8),
        "sql": """SELECT sector AS "Setor",
                         round(max(value) FILTER (WHERE metric = 'ari_entre_representacoes')::numeric, 3) AS "Concordância das partições (ARI)",
                         round(max(value) FILTER (WHERE metric = 'vizinhos_em_comum_de_10')::numeric, 2) AS "Vizinhos em comum (de 10)"
                  FROM gold.subgroup_analysis WHERE analysis = 'embeddings' GROUP BY sector ORDER BY sector""",
    },
]

OPERATION_CARDS = [
    {
        "name": "Chamadas pela API",
        "display": "scalar",
        "pos": (0, 0, 6, 3),
        "sql": "SELECT count(*) FROM ops.predictions WHERE source = 'api'",
    },
    {
        "name": "Baixa confiança (%), API",
        "display": "scalar",
        "pos": (6, 0, 6, 3),
        "sql": "SELECT coalesce(round(avg(low_confidence::int)::numeric * 100, 1), 0) FROM ops.predictions WHERE source = 'api'",
    },
    {
        "name": "Latência mediana (ms), API",
        "display": "scalar",
        "pos": (12, 0, 6, 3),
        "sql": "SELECT coalesce(round(percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)::numeric, 1), 0) FROM ops.predictions WHERE source = 'api'",
    },
    {
        "name": "Concordância com o candidato em sombra (%)",
        "display": "scalar",
        "pos": (18, 0, 6, 3),
        "sql": "SELECT coalesce(round(avg(sector_agreement)::numeric * 100, 1), 0) FROM gold.v_shadow_agreement",
    },
    {
        "name": "Chamadas pela API por minuto",
        "display": "line",
        "pos": (0, 3, 12, 7),
        "sql": 'SELECT minute AS "Minuto", sum(calls) AS "Chamadas" FROM gold.v_minutely GROUP BY 1 ORDER BY 1',
        "settings": {
            "graph.dimensions": ["Minuto"],
            "graph.metrics": ["Chamadas"],
            "series_settings": {"Chamadas": {"color": BLUE}},
        },
    },
    {
        "name": "Deriva: % de chamadas com baixa confiança",
        "display": "line",
        "pos": (12, 3, 12, 7),
        "sql": """SELECT minute AS "Minuto", round(sum(calls * low_confidence_pct) / sum(calls), 1) AS "% baixa confiança"
                  FROM gold.v_minutely GROUP BY 1 ORDER BY 1""",
        "settings": {
            "graph.dimensions": ["Minuto"],
            "graph.metrics": ["% baixa confiança"],
            "series_settings": {"% baixa confiança": {"color": RED}},
        },
    },
    {
        "name": "Atribuição frágil por subgrupo (%), conjunto de dados",
        "display": "row",
        "pos": (0, 10, 12, 12),
        "sql": """SELECT subgroup_name AS "Subgrupo", round(ambiguous_rate * 100, 1) AS "% frágeis" FROM gold.v_subgroup_mix
                  WHERE source = 'dataset' ORDER BY 2 DESC""",
        "settings": bars("Subgrupo", "% frágeis", ORANGE),
    },
    {
        "name": "Checagens de deriva",
        "display": "table",
        "pos": (12, 10, 12, 6),
        "sql": """SELECT ts AS "Quando", status AS "Estado", calls AS "Chamadas na janela" FROM ops.drift_checks
                  ORDER BY ts DESC LIMIT 10""",
    },
    {
        "name": "Últimas chamadas pela API",
        "display": "table",
        "pos": (12, 16, 12, 6),
        "sql": """SELECT ts AS "Quando", sector AS "Setor", subgroup_name AS "Subgrupo",
                  round(sector_probability::numeric, 3) AS "Prob. do setor", ambiguous AS "Frágil", n_words AS "Palavras"
                  FROM ops.predictions WHERE source = 'api' ORDER BY ts DESC LIMIT 10""",
    },
]

DASHBOARDS = {
    "dados": (
        DATA_DASHBOARD,
        "O que há nas transcrições e como os setores se diferenciam",
        DATA_CARDS + SUBGROUP_CARDS,
    ),
    "modelos": (
        MODEL_DASHBOARD,
        "Comparação de modelos para o setor e análises dos subgrupos",
        MODEL_CARDS + SUBGROUP_MODEL_CARDS,
    ),
    "operacao": (OPERATION_DASHBOARD, "A API em uso: volume, confiança, deriva e modelo em sombra", OPERATION_CARDS),
}


class Metabase:
    def __init__(self, base_url: str):
        self.base, self.session = base_url.rstrip("/"), None

    def call(self, method, path, body=None):
        headers = {"Content-Type": "application/json"}
        if self.session:
            headers["X-Metabase-Session"] = self.session
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data, headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"{method} {path}: {error.code} {error.read().decode()[:300]}") from error

    def wait_until_ready(self, tries=120):
        for _ in range(tries):
            try:
                if self.call("GET", "/api/health").get("status") == "ok":
                    return
            except (urllib.error.URLError, RuntimeError, ConnectionError):
                pass
            time.sleep(2)
        raise TimeoutError("o Metabase não respondeu")

    def sign_in(self, email, password):
        credentials = {"username": email, "password": password}
        try:
            self.session = self.call("POST", "/api/session", credentials)["id"]
        except RuntimeError:
            setup_token = self.call("GET", "/api/session/properties")["setup-token"]
            self.call(
                "POST",
                "/api/setup",
                {
                    "token": setup_token,
                    "prefs": {"site_name": "Callseg", "allow_tracking": False},
                    "user": {"first_name": "Callseg", "last_name": "Admin", "email": email, "password": password},
                },
            )
            self.session = self.call("POST", "/api/session", credentials)["id"]

    def ensure_database(self, name, details):
        databases = self.call("GET", "/api/database")
        databases = databases["data"] if isinstance(databases, dict) else databases
        found = [database for database in databases if database["name"] == name]
        database_id = (
            found[0]["id"]
            if found
            else self.call("POST", "/api/database", {"engine": "postgres", "name": name, "details": details})["id"]
        )
        self.call("POST", f"/api/database/{database_id}/sync_schema")
        time.sleep(8)
        return database_id

    def upsert_card(self, card, database_id, existing):
        body = {
            "name": card["name"],
            "display": card["display"],
            "visualization_settings": card.get("settings", {}),
            "dataset_query": {"type": "native", "database": database_id, "native": {"query": sql(card["sql"])}},
        }
        if card["name"] in existing:
            return self.call("PUT", f"/api/card/{existing[card['name']]}", body)
        return self.call("POST", "/api/card", {**body, "collection_id": None})

    def upsert_dashboard(self, name, description, cards, database_id):
        dashboards = {dashboard["name"]: dashboard["id"] for dashboard in self.call("GET", "/api/dashboard")}
        existing_cards = {card["name"]: card["id"] for card in self.call("GET", "/api/card")}
        dashboard_id = (
            dashboards.get(name)
            or self.call("POST", "/api/dashboard", {"name": name, "description": description})["id"]
        )
        layout = []
        for position, item in enumerate(cards):
            column, row, width, height = item["pos"]
            base = {"id": -(position + 1), "row": row, "col": column, "size_x": width, "size_y": height}
            if "text" in item:
                virtual = {
                    "name": None,
                    "display": "text",
                    "visualization_settings": {},
                    "dataset_query": {},
                    "archived": False,
                }
                layout.append(
                    {**base, "card_id": None, "visualization_settings": {"text": item["text"], "virtual_card": virtual}}
                )
            else:
                layout.append({**base, "card_id": self.upsert_card(item, database_id, existing_cards)["id"]})
        self.call(
            "PUT", f"/api/dashboard/{dashboard_id}", {"name": name, "description": description, "dashcards": layout}
        )
        return dashboard_id

    def public_uuid(self, dashboard_id):
        self.call("PUT", "/api/setting/enable-public-sharing", {"value": True})
        current = self.call("GET", f"/api/dashboard/{dashboard_id}").get("public_uuid")
        return current or self.call("POST", f"/api/dashboard/{dashboard_id}/public_link")["uuid"]


HUB_STYLE = """
:root{color-scheme:dark}
body{margin:0;background:#0e141b;color:#e8edf2;font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{display:flex;align-items:center;gap:14px;padding:16px 24px;background:#0a1017}
header img{width:40px;height:40px}header h1{margin:0;font-size:1.25rem}header p{margin:0;opacity:.7;font-size:.85rem}
main{max-width:900px;margin:0 auto;padding:24px 16px 64px}
a.card{display:block;background:#17202a;border:1px solid #26323f;border-radius:12px;padding:18px;margin-bottom:14px;color:inherit;text-decoration:none}
a.card:hover{border-color:#2a6f97}a.card h2{margin:0 0 4px;font-size:1.1rem}a.card p{margin:0;color:#93a1b0}
a.card span{color:#5aa9d6;font-size:.85rem}
"""
LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#14202e"/>'
    '<g stroke-linecap="round" stroke-width="5"><path d="M14 28v8M22 20v24" stroke="#2a6f97"/>'
    '<path d="M30 14v36M38 22v20" stroke="#e07a1f"/><path d="M46 17v30M54 27v10" stroke="#5a9e6f"/></g></svg>'
)


def write_hub(hub_dir: Path, public_paths: dict[str, str]):
    """Página inicial e um redirecionamento curto por painel."""
    hub_dir.mkdir(parents=True, exist_ok=True)
    cards = ""
    for slug, (title, description, _) in DASHBOARDS.items():
        cards += (
            f'<a class="card" href="/{slug}"><h2>{html.escape(title)}</h2><p>{html.escape(description)}</p>'
            f"<span>/{slug}</span></a>"
        )
        folder = hub_dir / slug
        folder.mkdir(exist_ok=True)
        target = f"{public_paths[slug]}{DARK_THEME}"
        (folder / "index.html").write_text(
            f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={target}">'
            f'<script>location.replace("{target}")</script><a href="{target}">Abrir o painel</a>'
        )
    page = (
        f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Callseg BI</title><style>{HUB_STYLE}</style></head><body>"
        f"<header>{LOGO}<div><h1>Callseg BI</h1><p>Análises do segmentador de chamadas</p></div></header>"
        f"<main>{cards}</main></body></html>"
    )
    (hub_dir / "index.html").write_text(page)


def main():
    environment = os.environ
    metabase = Metabase(environment.get("METABASE_URL", "http://127.0.0.1:3010"))
    metabase.wait_until_ready()
    metabase.sign_in(environment["METABASE_ADMIN_EMAIL"], environment["METABASE_ADMIN_PASSWORD"])
    database_id = metabase.ensure_database(
        "Callseg",
        {
            "host": "db",
            "port": 5432,
            "dbname": environment["POSTGRES_DB"],
            "user": "bi_reader",
            "password": environment["BI_PASSWORD"],
            "ssl": False,
        },
    )
    public_paths = {}
    for slug, (name, description, cards) in DASHBOARDS.items():
        dashboard_id = metabase.upsert_dashboard(name, description, cards, database_id)
        public_paths[slug] = f"/public/dashboard/{metabase.public_uuid(dashboard_id)}"
        print(f"{slug}: {public_paths[slug]}")
    write_hub(Path(environment.get("HUB_DIR", "hub")), public_paths)


if __name__ == "__main__":
    main()
