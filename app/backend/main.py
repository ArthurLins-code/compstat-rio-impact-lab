"""Aplicação FastAPI do CompStat Rio.

Monta todos os routers (preenchidos pelas trilhas). O servidor sobe mesmo com routers
ainda vazios, permitindo que cada trilha desenvolva e teste de forma isolada.

Rodar (a partir da raiz do repo):
    .venv/bin/uvicorn app.backend.main:app --reload
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .routers import acoes, ai, areas, copilot, export, match, report

app = FastAPI(title="CompStat Rio — Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(areas.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(match.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(copilot.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(acoes.router, prefix="/api")


@app.on_event("startup")
def _startup():
    """Cria as tabelas do SQLite no primeiro boot quando o flag está ligado."""
    if config.PERSISTENT_STATE:
        from .db import init_db
        init_db()


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "areas": config.AREA_FM_IDS,
        "model": config.MODEL,
        "has_api_key": config.has_api_key(),
        "persistent_state": config.PERSISTENT_STATE,
    }
