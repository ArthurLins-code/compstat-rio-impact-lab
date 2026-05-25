"""Aplicação FastAPI do CompStat Rio.

Monta todos os routers (preenchidos pelas trilhas). O servidor sobe mesmo com routers
ainda vazios, permitindo que cada trilha desenvolva e teste de forma isolada.

Rodar (a partir da raiz do repo):
    .venv/bin/uvicorn app.backend.main:app --reload
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .middleware.logging import RequestLoggingMiddleware
from .routers import acoes, ai, areas, copilot, export, match, report


def _validar_cors_em_producao(origins):
    """`"*"` em CORS_ORIGINS é incompatível com PERSISTENT_STATE (sem login).

    Sem login, qualquer origem alcançar o backend significa qualquer página
    web poder editar o relatório. Quando o flag está ligado, exigimos lista
    explícita de origens.
    """
    if config.PERSISTENT_STATE and ("*" in origins or any(o.strip() == "*" for o in origins)):
        raise RuntimeError(
            "CORS_ORIGINS='*' não é permitido com COMPSTAT_PERSISTENT_STATE=1 "
            "(sem login). Defina os domínios explícitos do app."
        )


_validar_cors_em_producao(config.CORS_ORIGINS)


# Logger raiz: handler simples em stdout. Quem subir em produção redireciona
# `compstat.req` para o coletor (Loki/CloudWatch/etc.).
logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="CompStat Rio — Backend", version="0.1.0")

app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
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

    # Scheduler embutido (Fase 5 / Tarefa 5.1) — opt-in via env. Em dev
    # default off para não poluir o terminal de quem só está editando o app.
    import os
    if os.environ.get("COMPSTAT_SCHEDULER_ON", "0").lower() in {"1", "true", "yes", "on"}:
        from .jobs import scheduler, tarefas

        h_refresh = int(os.environ.get("COMPSTAT_REFRESH_1746_H", "24"))
        m_health = int(os.environ.get("COMPSTAT_HEALTH_INTERVAL_M", "60"))
        scheduler.agendar("refresh_1746", h_refresh * 3600, tarefas.refresh_1746)
        scheduler.agendar("checar_frescor", m_health * 60, tarefas.checar_frescor, rodar_agora=True)
        scheduler.agendar("expurgar_cache", 24 * 3600, tarefas.expurgar_cache_velho)


@app.on_event("shutdown")
def _shutdown():
    """Cancela timers do scheduler — evita threads zumbi em testes/reload."""
    try:
        from .jobs import scheduler
        scheduler.parar()
    except Exception:  # pragma: no cover
        pass


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "areas": config.AREA_FM_IDS,
        "model": config.MODEL,
        "has_api_key": config.has_api_key(),
        "persistent_state": config.PERSISTENT_STATE,
    }
