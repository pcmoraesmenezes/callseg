"""Registro no MLflow: as execuções da comparação de modelos e o modelo vigente como versão do registro."""

import json
from pathlib import Path

import pandas as pd

from call_segmenter.models import CallSegmenter

from .artifacts import read_metadata

EXPERIMENT = "call-segmenter"
REGISTERED_MODEL = "call-segmenter"
EXPERIMENT_KIND_TAG = "mlflow.experimentKind"


def _define_pyfunc():
    import mlflow.pyfunc

    class SegmenterModel(mlflow.pyfunc.PythonModel):
        """Empacota o segmentador para o MLflow: entrada `text`, saída com setor e subgrupo."""

        def load_context(self, context):
            self.segmenter = CallSegmenter.load(context.artifacts["segmenter"])

        def predict(self, context, model_input, params=None):
            results = self.segmenter.predict(model_input["text"].tolist())
            return pd.DataFrame(
                {
                    "sector": [r.sector for r in results],
                    "sector_probability": [r.sector_probability for r in results],
                    "subgroup": [r.subgroup.name for r in results],
                    "low_confidence": [r.low_confidence for r in results],
                }
            )

    return SegmenterModel


def log_benchmark_runs(benchmark: dict) -> None:
    """Uma execução por candidato avaliado no caderno, com a etapa como tag."""
    import mlflow

    def run(name, stage, params, metrics):
        with mlflow.start_run(run_name=name, tags={"etapa": stage}):
            mlflow.log_params(
                {k: json.dumps(v) if isinstance(v, (list, tuple, dict)) else v for k, v in params.items()}
            )
            mlflow.log_metrics({k: float(v) for k, v in metrics.items() if v is not None})

    for item in benchmark["lazy"]:
        run(
            item["model"],
            "triagem",
            {"representacao": "tfidf_svd300"},
            {"f1_macro": item["f1_macro"], "seconds": item["seconds"]},
        )
    for item in benchmark["families_cv"]:
        run(
            item["model"],
            "validacao_cruzada",
            {},
            {"f1_macro": item["f1_validation"], "f1_std": item["std"], "fit_seconds": item["fit_seconds"]},
        )
    for position, item in enumerate(benchmark["wide_random_search"], 1):
        run(
            f"{item['family']} #{position}",
            "busca_aleatoria",
            item["parameters"],
            {"f1_macro": item["f1_macro"], "f1_std": item["std"], "fit_seconds": item["fit_seconds"]},
        )
    for item in benchmark["test"]:
        run(
            item["model"],
            "teste",
            {},
            {"f1_macro": item["f1_macro"], "errors": item["errors"], "ece": item["ece"], "accuracy": item["accuracy"]},
        )


def log_champion(model_path: str, figures_dir: str | None = None) -> str:
    """Registra o modelo vigente: parâmetros, medidas, figuras e o modelo como versão do registro.

    Returns:
        URI do modelo registrado.
    """
    import mlflow
    import mlflow.pyfunc

    metadata = read_metadata(model_path)
    segmenter = CallSegmenter.load(model_path)
    with mlflow.start_run(
        run_name=f"vigente {segmenter.model_version}",
        tags={"etapa": "producao", "model_version": segmenter.model_version},
    ):
        mlflow.log_params(
            {
                "estimator": segmenter.estimator,
                "regularization": segmenter.regularization,
                "low_confidence_threshold": segmenter.low_confidence_threshold,
                "n_train": segmenter.n_train,
                **{f"k_{sector}": k for sector, k in segmenter.cluster_counts.items()},
            }
        )
        mlflow.log_dict(metadata, "metadata.json")
        for figure in sorted(Path(figures_dir).glob("*.png")) if figures_dir and Path(figures_dir).exists() else []:
            mlflow.log_artifact(str(figure), "figures")
        info = mlflow.pyfunc.log_model(
            name="segmenter",
            python_model=_define_pyfunc()(),
            artifacts={"segmenter": model_path},
            input_example=pd.DataFrame({"text": ["thank you for calling, how can I help you today"]}),
            pip_requirements=["scikit-learn", "pandas", "numpy", "scipy", "joblib"],
            registered_model_name=REGISTERED_MODEL,
        )
    return info.model_uri


def log_all(model_path: str, benchmark_path: str | None, figures_dir: str | None) -> dict:
    """Recria o experimento: execuções da comparação, modelo vigente e a marca de experimento de treino de modelo."""
    import mlflow

    experiment = mlflow.set_experiment(EXPERIMENT)
    mlflow.MlflowClient().set_experiment_tag(experiment.experiment_id, EXPERIMENT_KIND_TAG, "custom_model_development")
    for old in mlflow.search_runs([experiment.experiment_id], output_format="list"):
        mlflow.delete_run(old.info.run_id)
    if benchmark_path and Path(benchmark_path).exists():
        log_benchmark_runs(json.loads(Path(benchmark_path).read_text()))
    return {"registered_model": log_champion(model_path, figures_dir)}
