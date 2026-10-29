"""Rotas de segmentação."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response

from ..schemas import Batch, Call, Segmentation
from ..services.segmentation import SegmentationService

router = APIRouter()
EXPLAIN = Query(False, description="Inclui os termos que sustentam a decisão.")


def get_service(request: Request) -> SegmentationService:
    """Entrega o serviço montado na partida da aplicação."""
    return request.app.state.service


@router.post("/segment", response_model=Segmentation)
def segment_one(
    call: Call,
    response: Response,
    background: BackgroundTasks,
    explain: bool = EXPLAIN,
    service: SegmentationService = Depends(get_service),
):
    """Segmenta uma chamada: devolve o setor e o subgrupo dentro dele."""
    request_id = uuid.uuid4().hex
    outcomes = service.segment([call.text], request_id, explain)
    background.add_task(service.persist, [call.text], outcomes)
    response.headers["X-Request-ID"] = request_id
    return outcomes[0].response


@router.post("/segment/batch", response_model=list[Segmentation])
def segment_batch(
    batch: Batch,
    response: Response,
    background: BackgroundTasks,
    explain: bool = EXPLAIN,
    service: SegmentationService = Depends(get_service),
):
    """Segmenta até 50 chamadas; a resposta mantém a ordem da entrada."""
    request_id = uuid.uuid4().hex
    transcripts = [call.text for call in batch.calls]
    outcomes = service.segment(transcripts, request_id, explain)
    background.add_task(service.persist, transcripts, outcomes)
    response.headers["X-Request-ID"] = request_id
    return [outcome.response for outcome in outcomes]


@router.get("/subgroups")
def subgroup_catalog(service: SegmentationService = Depends(get_service)):
    """Catálogo dos subgrupos de cada setor: nome, tamanho no treino e termos de maior peso."""
    return service.segmenter.subgroup_catalog_summary()


@router.get("/recent")
def recent_predictions(limit: int = Query(20, ge=1, le=100), service: SegmentationService = Depends(get_service)):
    """Últimas predições feitas pela API (vazio se não houver banco)."""
    return service.repository.recent(limit)
