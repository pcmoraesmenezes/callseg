# Airflow com o pacote do projeto em um ambiente à parte (/opt/callseg), para as bibliotecas de ciência de dados
# não brigarem com as do Airflow. As tarefas do DAG chamam o comando `callseg` desse ambiente.
FROM apache/airflow:2.10.5-python3.10
USER root
COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /usr/local/bin/uv
RUN mkdir /opt/callseg /src && chown airflow /opt/callseg /src
USER airflow
WORKDIR /src
COPY --chown=airflow pyproject.toml uv.lock .python-version ./
COPY --chown=airflow src ./src
ENV UV_PROJECT_ENVIRONMENT=/opt/callseg UV_LINK_MODE=copy
RUN uv sync --frozen --no-dev --no-editable
COPY --chown=airflow airflow/dags /opt/airflow/dags
