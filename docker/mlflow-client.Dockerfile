# Cliente MLflow com o pacote do projeto: registra execuções e o modelo no servidor do compose.
FROM python:3.10-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --extra mlops --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --extra mlops --no-editable

FROM python:3.10-slim
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
USER app
