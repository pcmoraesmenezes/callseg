"""Resultados da comparação de modelos (gerados pelo caderno) levados ao banco para o painel."""

import json
import uuid
from pathlib import Path

from sqlalchemy import delete

from call_segmenter.warehouse.models import ModelBenchmark, SubgroupAnalysis


def benchmark_rows(benchmark: dict, run_id: str) -> list[ModelBenchmark]:
    """Transforma o `benchmark.json` do caderno em linhas de `ops.model_benchmark`."""
    rows = []
    for item in benchmark["lazy"]:
        rows.append(
            ModelBenchmark(
                run_id=run_id,
                stage="triagem",
                model=item["model"],
                representation="tfidf_svd300",
                f1_macro=item["f1_macro"],
                accuracy=item["accuracy"],
                fit_seconds=item["seconds"],
            )
        )
    for item in benchmark["families_cv"]:
        rows.append(
            ModelBenchmark(
                run_id=run_id,
                stage="validacao_cruzada",
                model=item["model"],
                representation="tfidf",
                f1_macro=item["f1_validation"],
                fit_seconds=item["fit_seconds"],
                parameters={"f1_std": item["std"], "f1_train": item["f1_train"]},
            )
        )
    for position, item in enumerate(benchmark["wide_random_search"], 1):
        rows.append(
            ModelBenchmark(
                run_id=run_id,
                stage="busca_aleatoria",
                model=item["family"],
                representation="tfidf",
                trial=position,
                f1_macro=item["f1_macro"],
                fit_seconds=item["fit_seconds"],
                parameters={**item["parameters"], "f1_std": item["std"]},
            )
        )
    for item in benchmark["test"]:
        rows.append(
            ModelBenchmark(
                run_id=run_id,
                stage="teste",
                model=item["model"],
                f1_macro=item["f1_macro"],
                accuracy=item["accuracy"],
                errors=item["errors"],
                ece=item["ece"],
            )
        )
    return rows


def load_benchmark(session_factory, path: str) -> int:
    """Substitui o conteúdo de `ops.model_benchmark` pelo do arquivo. Devolve o número de linhas."""
    benchmark = json.loads(Path(path).read_text())
    rows = benchmark_rows(benchmark, uuid.uuid4().hex[:8])
    with session_factory() as session:
        session.execute(delete(ModelBenchmark))
        session.add_all(rows)
        session.commit()
    return len(rows)


def subgroup_rows(subgroups: dict) -> list[SubgroupAnalysis]:
    """Transforma a seção `subgrupos` do `metrics.json` em linhas de `gold.subgroup_analysis`."""
    rows = []

    def add(analysis, sector, label, metrics):
        rows.extend(
            SubgroupAnalysis(analysis=analysis, sector=sector, label=str(label), metric=name, value=value)
            for name, value in metrics.items()
        )

    for item in subgroups["escolha_de_k"]:
        add(
            "escolha_de_k",
            item["setor"],
            item["k"],
            {"silhueta": item["silhueta"], "estabilidade": item["estabilidade"], "menor_grupo": item["menor grupo"]},
        )
    for item in subgroups["algoritmos"]:
        add(
            "algoritmos",
            item["setor"],
            item["algoritmo"],
            {
                "estabilidade": item["estabilidade"],
                "silhueta": item["silhueta"],
                "ruido": item["chamadas como ruído"],
                "concordancia_com_kmeans": item["concordância com KMeans (ARI)"],
            },
        )
    for item in subgroups["vizinhanca"]:
        add(
            "vizinhanca",
            item["setor"],
            "KMeans sobre TF-IDF",
            {
                "pureza_media": item["pureza média de vizinhança"],
                "pureza_do_grupo_mais_fraco": item["pureza do grupo mais fraco"],
                "teste_centro_e_vizinhos_concordam": item["chamadas de teste: centro e vizinhos concordam"],
            },
        )
    for item in subgroups["embeddings"]:
        add(
            "embeddings",
            item["setor"],
            "TF-IDF contra embedding",
            {
                "estabilidade_tfidf": item["estabilidade TF-IDF"],
                "estabilidade_embedding": item["estabilidade embedding"],
                "ari_entre_representacoes": item["ARI entre TF-IDF e embedding"],
                "vizinhos_em_comum_de_10": item["vizinhos em comum (de 10)"],
            },
        )
    return rows


def load_subgroup_analysis(session_factory, metrics_path: str) -> int:
    """Substitui o conteúdo de `gold.subgroup_analysis` pelo da seção `subgrupos` do `metrics.json`."""
    rows = subgroup_rows(json.loads(Path(metrics_path).read_text())["subgrupos"])
    with session_factory() as session:
        session.execute(delete(SubgroupAnalysis))
        session.add_all(rows)
        session.commit()
    return len(rows)
