"""Escolhas de produção do segmentador. Cada valor tem sua justificativa em `docs/adr/`."""

import json
from importlib import resources

SEED = 0
CLUSTER_COUNTS = {"automotive": 6, "home_service": 8, "medicare": 7}
SECTOR_ESTIMATOR = "svm_calibrated"
SECTOR_REGULARIZATION = 5.0
LOW_CONFIDENCE_THRESHOLD = 0.9
LATENCY_BUDGET_MS = 50.0


def load_subgroup_catalog() -> dict[str, list[dict]]:
    """Nomes e âncoras dos subgrupos, por setor, lidos de `models/subgroup_names.json`."""
    text = resources.files("call_segmenter.models").joinpath("subgroup_names.json").read_text()
    return json.loads(text)
