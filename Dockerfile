# Backend FastAPI do CompStat Rio.
#
# Build:
#   docker build -t compstat-backend .
# Run (standalone):
#   docker run --rm -p 8010:8010 \
#     -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
#     -v "$PWD/dados_normalizados:/app/dados_normalizados:ro" \
#     compstat-backend
#
# O uso normal é via docker-compose.yml (sobe backend + frontend juntos).

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Shapely 2.x wheel já trai libgeos embutido; não precisamos instalar gdal
# (o repo não usa geopandas/fiona/gdal — confirmado por grep em 2026-05).
# build-essential cobre qualquer wheel que ainda precise compilar (raro em slim).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Camada de deps separada para aproveitar cache do Docker.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Código da app + pipeline de normalização (backend importa normalizacao.config).
COPY app/ ./app/
COPY normalizacao/ ./normalizacao/

# Esquema canônico não-root.
RUN useradd --create-home --shell /bin/bash compstat \
 && chown -R compstat:compstat /app
USER compstat

EXPOSE 8010

# Healthcheck simples: /api/health responde 200 mesmo sem chave Anthropic.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/api/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8010"]
