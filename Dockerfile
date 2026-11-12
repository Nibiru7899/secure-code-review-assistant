FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
RUN apt-get update && apt-get install -y --no-install-recommends cppcheck=2.10-2 && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY requirements.docker.lock ./
RUN --mount=type=cache,target=/root/.cache/pip pip install torch==2.6.0+cpu --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.docker.lock && pip check
COPY pyproject.toml ./
COPY app ./app
COPY ui ./ui
COPY rules ./rules
COPY .streamlit ./.streamlit
COPY scripts/__init__.py scripts/migrate_postgres.py ./scripts/
RUN useradd --uid 10001 --create-home reviewer && mkdir -p /data/data /data/analysis && chown -R reviewer:reviewer /data /workspace
USER reviewer
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
