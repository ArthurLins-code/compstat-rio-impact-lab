"""Router de áreas e mapa — Trilha 1 (Dados & Match).

  GET /areas               -> List[AreaInfo]
  GET /areas/{id}/map      -> GeoJSON (ocorrências, polígono, câmeras, fatores, segmentos críticos)
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks

from .. import deps
from ..ai import jobs as J
from ..data import duck as D
from ..data import geojson as G
from ..match.engine import compute_match
from ..report import models as M

router = APIRouter()


@router.get("/areas", response_model=List[M.AreaInfo])
def get_areas() -> List[M.AreaInfo]:
    return [
        M.AreaInfo(
            areaId=a["area_fm_id"],
            nomeArea=a["nome_area"],
            totalOcorrencias=a["total_ocorrencias"],
            scoreArea=None,
        )
        for a in D.listar_areas()
    ]


@router.get("/areas/overview", response_model=List[M.AreaResumo])
def get_areas_overview() -> List[M.AreaResumo]:
    """Resumo das áreas FM (ordenado por urgência) para a página inicial."""
    return [M.AreaResumo(**a) for a in D.resumo_areas()]


@router.post("/areas/{area_id}/reprocessar-dinamica", status_code=202)
def reprocessar_dinamica(area_id: int, bg: BackgroundTasks) -> Dict[str, Any]:
    """Agenda re-extração da dinâmica criminal da área (Tarefa 3.6).

    Devolve 202 imediato com `job_id` + `estimativa_custo_usd` calculada a
    partir do nº de RELINTs e do custo médio histórico do prompt de
    extração. Estado do job sobrevive na RAM do processo até a Fase 5
    trazer um orquestrador (Celery/Prefect).
    """
    job = J.criar_job("reprocessar_dinamica", area_id)
    bg.add_task(J.rodar_reprocessar_dinamica, job.job_id)
    return {
        "jobId": job.job_id,
        "status": "agendado",
        "estimativaCustoUsd": job.estimativa_custo_usd,
        "consultarStatusEm": "/api/jobs/%s" % job.job_id,
    }


@router.get("/jobs/{job_id}")
def status_job(job_id: str):
    """Estado de um job assíncrono (reprocessar-dinamica, etc.)."""
    from fastapi import HTTPException
    j = J.obter(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return j


@router.get("/areas/{area_id}/map")
def get_area_map(area_id: int) -> Dict[str, Any]:
    # Ocorrências (pontos).
    occ_features = [
        G.point_feature(
            o["lon"],
            o["lat"],
            {"category": o["category"], "hora": o["hora"], "dia_semana": o["dia_semana"]},
        )
        for o in D.ocorrencias_geo(area_id)
    ]

    # Câmeras (pontos).
    cam_features = [
        G.point_feature(c["lon"], c["lat"], {"category": c["category"]})
        for c in D.cameras_geo(area_id)
    ]

    # Fatores urbanos (pontos).
    fat_features = [
        G.point_feature(
            f["lon"], f["lat"], {"category": f["category"], "orgao": f["orgao"]}
        )
        for f in D.fatores_geo(area_id)
    ]

    # Polígono da área (de dim_area_fm).
    poly_row = deps.query_one(
        "SELECT geometry_wkt, nome_subarea FROM read_csv_auto('%s') WHERE area_fm_id = ?"
        % deps.silver("dim_area_fm.csv"),
        [area_id],
    )
    if poly_row and poly_row.get("geometry_wkt"):
        area_polygon = G.feature(
            G.wkt_to_geojson(poly_row["geometry_wkt"]),
            {"area_fm_id": area_id, "nome": poly_row.get("nome_subarea", "")},
        )
    else:
        area_polygon = None

    # Segmentos críticos (coincidências do match).
    match = compute_match(area_id)
    crit_features = [
        G.point_feature(
            c.lon,
            c.lat,
            {
                "id": c.id,
                "score": c.score,
                "justificativa": c.justificativa,
                "camadas": c.camadas,
                "nOcorrencias": c.nOcorrencias,
            },
        )
        for c in match.coincidencias
    ]

    return {
        "occurrences": G.feature_collection(occ_features),
        "areaPolygon": area_polygon,
        "cameras": G.feature_collection(cam_features),
        "urbanFactors": G.feature_collection(fat_features),
        "criticalSegments": G.feature_collection(crit_features),
    }
