"""Router do Plano de Ação (Fase 2 / Tarefa 2.3).

Endpoints (prefixo /api adicionado em main.py):
  GET    /areas/{area_id}/acoes?status=...     -> lista (seed automático se vazio)
  POST   /areas/{area_id}/acoes                -> cria nova ação manual
  PATCH  /acoes/{id}                           -> atualiza (transição/responsavel/...)
  GET    /acoes/{id}/historico                 -> transições registradas

Requer `PERSISTENT_STATE=1`. Sem o flag, responde 503 com mensagem clara —
o frontend pode degradar para a lista derivada de `sec_plano_acao`.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from .. import config

router = APIRouter()


def _exige_persistencia() -> None:
    if not config.PERSISTENT_STATE:
        raise HTTPException(
            status_code=503,
            detail="Plano de Ação persistente requer COMPSTAT_PERSISTENT_STATE=1.",
        )


class AcaoCreate(BaseModel):
    acao: str
    responsavel: Optional[str] = None
    prazo: Optional[date] = None
    origemAcaoId: Optional[str] = None


class AcaoPatch(BaseModel):
    status: Optional[str] = None
    responsavel: Optional[str] = None
    prazo: Optional[date] = None
    evidencia: Optional[str] = None
    observacao: Optional[str] = None  # acompanha a transição no histórico
    ator: Optional[str] = "anonimo"


@router.get("/areas/{area_id}/acoes")
def listar_acoes(
    area_id: int,
    status: Optional[str] = Query(None, description="Filtra por status (opcional)."),
) -> List[Dict[str, Any]]:
    _exige_persistencia()
    from ..db import acoes as A
    from ..report import sections as S

    atual = A.listar(area_id, status=status)
    # Seed automático: se a área ainda não tem nenhuma ação, popula com as
    # propostas derivadas de sec_plano_acao (mesma lista que o relatório usa).
    if not atual and status is None:
        propostas = [p.model_dump() for p in S.sec_plano_acao(area_id)]
        A.seed_da_area(area_id, propostas, ator="sistema-seed")
        atual = A.listar(area_id, status=status)
    return atual


@router.post("/areas/{area_id}/acoes")
def criar_acao(area_id: int, body: AcaoCreate) -> Dict[str, Any]:
    _exige_persistencia()
    from ..db import acoes as A
    return A.criar(
        area_id=area_id,
        acao=body.acao,
        responsavel=body.responsavel,
        prazo=body.prazo,
        origem_acao_id=body.origemAcaoId,
    )


@router.patch("/acoes/{acao_id}")
def atualizar_acao(acao_id: int, body: AcaoPatch = Body(...)) -> Dict[str, Any]:
    _exige_persistencia()
    from ..db import acoes as A
    try:
        return A.atualizar(
            acao_id,
            status=body.status,
            responsavel=body.responsavel,
            prazo=body.prazo,
            evidencia=body.evidencia,
            observacao=body.observacao,
            ator=body.ator or "anonimo",
        )
    except A.AcaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
    except A.TransicaoInvalida as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/acoes/{acao_id}/historico")
def historico_acao(acao_id: int) -> List[Dict[str, Any]]:
    _exige_persistencia()
    from ..db import acoes as A
    try:
        return A.historico(acao_id)
    except A.AcaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e))
