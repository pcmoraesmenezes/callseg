# Imagem da API e das etapas do pipeline (callseg ...). Só dependências de execução, sem notebook nem MLflow.
FROM python:3.10-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.10-slim
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY backend ./backend
COPY frontend ./frontend
ENV PATH=/app/.venv/bin:$PATH PYTHONPATH=/app/backend PYTHONUNBUFFERED=1 \
    MODEL_PATH=/models/segmenter.joblib FRONTEND_DIR=/app/frontend
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
