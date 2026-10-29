"""Métricas no formato Prometheus."""

from prometheus_client import Counter, Histogram

REQUESTS = Counter("segment_requests_total", "Chamadas segmentadas", ["sector"])
AMBIGUOUS = Counter("segment_ambiguous_total", "Subgrupos marcados como ambíguos", ["sector"])
LOW_CONFIDENCE = Counter("segment_low_confidence_total", "Setores com baixa confiança")
LATENCY = Histogram(
    "segment_latency_seconds", "Latência por chamada", buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1)
)
SHADOW_DISAGREEMENT = Counter(
    "segment_shadow_disagreement_total", "Chamadas em que o candidato discorda do vigente", ["field"]
)
