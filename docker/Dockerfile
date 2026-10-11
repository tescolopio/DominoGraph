FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////app/data/dominograph.db

WORKDIR /app
COPY pyproject.toml /app/
COPY core /app/core
COPY schemas /app/schemas
COPY collectors /app/collectors
COPY transforms /app/transforms
COPY agents /app/agents
COPY orchestration /app/orchestration
COPY api /app/api
COPY scripts /app/scripts
COPY frontend /app/frontend
COPY data/examples /app/data/examples
RUN pip install --no-cache-dir '.[postgres]' \
    && useradd --create-home --uid 10001 domino \
    && mkdir -p /app/data/raw \
    && chown -R domino:domino /app/data
USER domino
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
