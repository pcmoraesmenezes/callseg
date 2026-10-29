"""Montagem da aplicação FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from call_segmenter import CallSegmenter
from call_segmenter.warehouse import (
    NullPredictionRepository,
    PredictionRepository,
    create_db_engine,
    create_session_factory,
)

from .config import Settings
from .logging_config import configure_logging
from .routers import segmentation, system
from .services.segmentation import SegmentationService

DESCRIPTION = "Dada a transcrição completa de uma chamada, devolve o setor e o subgrupo dentro dele."


def build_service(settings: Settings) -> SegmentationService:
    """Carrega o modelo vigente, o candidato em sombra (se configurado) e o repositório de predições."""
    segmenter = CallSegmenter.load(settings.model_path)
    shadow = CallSegmenter.load(settings.shadow_model_path) if settings.shadow_model_path else None
    if settings.database_url:
        repository = PredictionRepository(create_session_factory(create_db_engine(settings.database_url)))
    else:
        repository = NullPredictionRepository()
    return SegmentationService(segmenter, repository, shadow)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Cria a aplicação. O modelo é carregado quando ela sobe, não na importação."""
    settings = settings or Settings()
    log = configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = build_service(settings)
        log.info(
            "modelo carregado",
            extra={
                "fields": {
                    "model_version": app.state.service.segmenter.model_version,
                    "store": app.state.service.repository.enabled,
                    "shadow": bool(app.state.service.shadow),
                }
            },
        )
        yield

    app = FastAPI(title="Segmentação de chamadas de call center", description=DESCRIPTION, lifespan=lifespan)
    app.include_router(segmentation.router)
    app.include_router(system.router)
    app.mount("/demo", StaticFiles(directory=settings.frontend_dir, html=True), name="demo")
    return app


app = create_app()
