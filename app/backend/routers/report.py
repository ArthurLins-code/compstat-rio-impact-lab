"""Router do relatório (determinístico) — Trilha 1 (Dados & Match).

  GET   /report/{id}                 -> Relatorio
  GET   /report/{id}/temporal        -> TemporalMatrix
  GET   /report/{id}/coincidencias   -> MatchResult
  PATCH /report/{id}/section/{secao} -> salva edição humana (estado em memória)
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Query

from ..match.engine import compute_match
from ..report import models as M
from ..report import periodo as P
from ..report import sections as S
from ..report.assembler import aplicar_edicao, get_relatorio

router = APIRouter()


@router.get("/report/{area_id}", response_model=M.Relatorio)
def get_report(
    area_id: int,
    periodo: str = Query(
        P.PRESET_DEFAULT,
        description="Recorte temporal. Presets: %s." % ", ".join(P.PRESETS),
    ),
) -> M.Relatorio:
    try:
        return get_relatorio(area_id, preset_periodo=periodo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/report/{area_id}/temporal", response_model=M.TemporalMatrix)
def get_report_temporal(
    area_id: int,
    periodo: str = Query(P.PRESET_DEFAULT),
) -> M.TemporalMatrix:
    try:
        _, janela = P.resolver(periodo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return S.sec_temporal(area_id, janela)


@router.get("/report/{area_id}/coincidencias", response_model=M.MatchResult)
def get_report_coincidencias(area_id: int) -> M.MatchResult:
    return compute_match(area_id)


@router.get("/report/{area_id}/versoes")
def listar_versoes(area_id: int):
    """Metadados das versões salvas do relatório (Tarefa 2.4).

    503 quando PERSISTENT_STATE=0 — sem persistência não há versões.
    """
    from .. import config
    if not config.PERSISTENT_STATE:
        raise HTTPException(
            status_code=503,
            detail="Versionamento requer COMPSTAT_PERSISTENT_STATE=1.",
        )
    from ..db import versoes as V
    return V.listar(area_id)


@router.get("/report/{area_id}/versoes/{versao}")
def obter_versao(area_id: int, versao: int):
    """Snapshot completo de uma versão específica."""
    from .. import config
    if not config.PERSISTENT_STATE:
        raise HTTPException(
            status_code=503,
            detail="Versionamento requer COMPSTAT_PERSISTENT_STATE=1.",
        )
    from ..db import versoes as V
    snap = V.obter(area_id, versao)
    if snap is None:
        raise HTTPException(status_code=404, detail="Versão não encontrada.")
    return snap


@router.patch("/report/{area_id}/section/{secao}")
def patch_report_section(
    area_id: int, secao: str, payload: Dict[str, Any] = Body(...)
) -> Dict[str, bool]:
    try:
        aplicar_edicao(area_id, secao, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}
