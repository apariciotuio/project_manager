# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---

FROM base AS dev

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Source is mounted at /app in dev (docker-compose volume mount)
EXPOSE 17004

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "17004", "--reload"]
