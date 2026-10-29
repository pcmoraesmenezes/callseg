# Servidor MLflow: rastreio dos experimentos e registro dos modelos, com os metadados no Postgres.
FROM python:3.10-slim
RUN pip install --no-cache-dir mlflow==3.10.1 psycopg2-binary==2.9.10 && \
    useradd --uid 10002 --no-create-home --shell /usr/sbin/nologin mlflow && \
    mkdir /mlartifacts && chown mlflow /mlartifacts
USER mlflow
EXPOSE 5000
CMD ["sh", "-c", "mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri \"$MLFLOW_BACKEND\" --artifacts-destination /mlartifacts --serve-artifacts --allowed-hosts \"$MLFLOW_ALLOWED_HOSTS\" --cors-allowed-origins \"$MLFLOW_CORS_ORIGINS\""]
