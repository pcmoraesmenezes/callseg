"""Rotas de operação: saúde, métricas e porta de entrada."""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import RedirectResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from ..services.segmentation import SegmentationService
from .segmentation import get_service

router = APIRouter()


@router.get("/health")
def health(service: SegmentationService = Depends(get_service)):
    """Estado do serviço e versão do modelo carregado."""
    segmenter = service.segmenter
    return {
        "status": "ok",
        "model_version": segmenter.model_version,
        "sectors": sorted(segmenter.clusterers),
        "sector_min_probability": segmenter.low_confidence_threshold,
        "prediction_log": service.repository.enabled,
        "shadow_model_version": service.shadow.model_version if service.shadow else None,
    }


@router.get("/metrics", include_in_schema=False)
def metrics():
    """Métricas no formato Prometheus."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/demo/")
