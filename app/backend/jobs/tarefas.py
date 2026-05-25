"""Tarefas operacionais agendadas (Tarefa 5.1).

Cada função é leve, idempotente e tolera falha sem propagar — o
scheduler já loga; estas só fazem o trabalho útil.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

_LOG = logging.getLogger("compstat.jobs")


# ---------------------------------------------------------------------------
# Frescor dos datasets críticos
# ---------------------------------------------------------------------------


# Caminho relativo a OUT (silver/gold) -> SLA em horas. Acima do SLA = âmbar
# (não vermelho — sinaliza para o gestor sem bloquear nada).
SLAS_HORAS: Dict[str, int] = {
    "gold/area_brief.csv": 168,             # gold ≤ 7 dias
    "gold/gold_temporal.csv": 168,
    "gold/gold_ocorrencias_tipo.csv": 168,
    "gold/gold_fatores_orgao.csv": 168,
    "silver/fact_ocorrencias.csv": 168,
    "silver/fact_chamados_1746.csv": 36,    # 1746 deve estar < 36h (carga diária)
}


def _idade_horas(p: Path) -> Optional[float]:
    if not p.exists():
        return None
    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    delta = datetime.now(tz=timezone.utc) - mtime
    return round(delta.total_seconds() / 3600, 1)


def _status(idade_h: Optional[float], sla_h: int) -> str:
    if idade_h is None:
        return "vermelho"  # arquivo ausente
    if idade_h <= sla_h:
        return "verde"
    if idade_h <= sla_h * 1.5:
        return "ambar"
    return "vermelho"


def relatorio_frescor() -> Dict:
    """Lista cada dataset com idade + status. Status geral = pior dos individuais."""
    from normalizacao import config as NC

    rows: List[Dict] = []
    pior = "verde"
    for caminho_rel, sla in SLAS_HORAS.items():
        p = NC.OUT / caminho_rel
        idade = _idade_horas(p)
        st = _status(idade, sla)
        rows.append(
            {
                "nome": caminho_rel,
                "idadeHoras": idade,
                "slaHoras": sla,
                "status": st,
                "presente": p.exists(),
            }
        )
        if st == "vermelho":
            pior = "vermelho"
        elif st == "ambar" and pior != "vermelho":
            pior = "ambar"

    return {
        "datasets": rows,
        "statusGeral": pior,
        "computadoEm": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
    }


def checar_frescor() -> None:
    """Tarefa do scheduler: emite log com o relatório de frescor.

    Não bloqueia nada — só registra. O endpoint `/api/health/data` faz a
    leitura em tempo real para o frontend.
    """
    r = relatorio_frescor()
    _LOG.info("frescor_geral=%s datasets=%d", r["statusGeral"], len(r["datasets"]))


# ---------------------------------------------------------------------------
# Refresh 1746 (BigQuery; fallback log quando sem credencial)
# ---------------------------------------------------------------------------


def refresh_1746() -> None:
    """Pull do 1746 do BigQuery + grava silver atualizado.

    Sem credencial GCP (caminho atual), apenas loga "skipped" — não erra.
    A integração real liga quando a Prefeitura ativar billing (Fase 5,
    pré-requisito documentado em proximas_ideias.MD).
    """
    if not (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or
            os.environ.get("COMPSTAT_GCP_PROJECT")):
        _LOG.info("refresh_1746 skipped: sem credencial GCP")
        return

    try:
        from normalizacao import ingest_1746 as IN
        from normalizacao import config as NC

        bruto = IN.from_bigquery(desde=(datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d"))
        norm = IN.normalize(bruto)
        out = NC.OUT_SILVER / "fact_chamados_1746.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        norm.to_csv(out, index=False)
        _LOG.info("refresh_1746 ok rows=%d destino=%s", len(norm), out)
    except Exception as e:
        _LOG.exception("refresh_1746 falhou: %s", e)


# ---------------------------------------------------------------------------
# Expurgo do cache de respostas
# ---------------------------------------------------------------------------


def expurgar_cache_velho(dias_sem_uso: int = 30) -> int:
    """Apaga entradas do RespostaCache não usadas há `dias_sem_uso`+ dias.

    Devolve a contagem expurgada. Sem PERSISTENT_STATE, no-op.
    """
    try:
        from .. import config
        if not config.PERSISTENT_STATE:
            return 0
        from ..db import get_session
        from ..db.models import RespostaCache

        corte = datetime.now(tz=timezone.utc) - timedelta(days=dias_sem_uso)
        with get_session() as s:
            n = (
                s.query(RespostaCache)
                .filter(RespostaCache.ultimo_uso_em < corte)
                .delete(synchronize_session=False)
            )
            _LOG.info("expurgar_cache_velho removidas=%d corte=%s", n, corte.isoformat())
            return n
    except Exception as e:
        _LOG.exception("expurgar_cache_velho falhou: %s", e)
        return 0
