"""Background jobs simples (Tarefa 3.6).

Apenas o necessário para o botão "reprocessar dinâmica da área": gerar
job_id, estimar custo, agendar via BackgroundTasks do FastAPI. NÃO é um
orquestrador real (Celery/Prefect) — isso entra na Fase 5.

Estado dos jobs vive em RAM. Como há, por desenho, baixo volume (gestor
clica raramente), e o processo não sobrevive a restart de servidor —
isso é aceitável até a Fase 5.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional


@dataclass
class Job:
    job_id: str
    tipo: str
    area_id: int
    status: str = "pendente"  # pendente | rodando | concluido | erro
    estimativa_custo_usd: float = 0.0
    iniciado_em: Optional[str] = None
    concluido_em: Optional[str] = None
    erro: Optional[str] = None
    detalhes: Dict = field(default_factory=dict)


_JOBS: Dict[str, Job] = {}
_LOCK = threading.Lock()


def _custo_medio_historico_usd() -> float:
    """Custo médio por execução de extração, lido de `copilot_eventos`.

    Sem histórico ou sem PERSISTENT_STATE, devolve 0.02 (Sonnet, ~6k in + 1k out).
    """
    try:
        from .. import config
        if not config.PERSISTENT_STATE:
            return 0.02
        from ..db import get_session
        from ..db.models import CopilotEvento

        with get_session() as s:
            rows = (
                s.query(CopilotEvento)
                .filter(CopilotEvento.prompt_nome == "extracao_dinamica")
                .all()
            )
            if not rows:
                return 0.02
            return float(
                sum((r.custo_usd or Decimal(0)) for r in rows) / Decimal(len(rows))
            )
    except Exception:
        return 0.02


def _contar_relints(area_id: int) -> int:
    """Conta arquivos RELINT da área. 0 quando o diretório não existe."""
    try:
        from normalizacao import config as NC

        d = NC.D_RELINTS
        if not d.exists():
            return 0
        # Heurística: 1 arquivo por relint; produção pode pré-filtrar por área.
        return sum(1 for _ in d.iterdir() if _.is_file())
    except Exception:
        return 0


def estimar_custo(area_id: int) -> Dict[str, float]:
    """Estimativa USD para reprocessar dinâmica da área (RELINTs × custo médio)."""
    n = _contar_relints(area_id)
    media = _custo_medio_historico_usd()
    return {
        "n_relints": n,
        "custo_medio_usd_por_relint": round(media, 4),
        "estimativa_total_usd": round(n * media, 4),
    }


def criar_job(tipo: str, area_id: int, **detalhes) -> Job:
    """Cria job pendente com estimativa de custo. Não roda — quem roda é o agendador."""
    job_id = uuid.uuid4().hex
    job = Job(
        job_id=job_id,
        tipo=tipo,
        area_id=area_id,
        estimativa_custo_usd=estimar_custo(area_id)["estimativa_total_usd"],
        detalhes=detalhes,
    )
    with _LOCK:
        _JOBS[job_id] = job
    return job


def obter(job_id: str) -> Optional[Dict]:
    with _LOCK:
        j = _JOBS.get(job_id)
        return asdict(j) if j else None


def _agora_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def rodar_reprocessar_dinamica(job_id: str) -> None:
    """Worker da extração de dinâmica. Chamado pelo BackgroundTasks do FastAPI.

    Hoje: stub que apenas marca o job como concluído. A pipeline real
    está em `normalizacao/run_llm.py` e será conectada quando o
    orquestrador da Fase 5 entrar em cena (evita executar LLM no thread
    do uvicorn).
    """
    with _LOCK:
        j = _JOBS.get(job_id)
        if j is None:
            return
        j.status = "rodando"
        j.iniciado_em = _agora_iso()

    try:
        # TODO Fase 5: invocar `normalizacao.run_llm` no orquestrador.
        # Por enquanto, devolve OK + observação para o gestor.
        with _LOCK:
            j = _JOBS[job_id]
            j.status = "concluido"
            j.concluido_em = _agora_iso()
            j.detalhes["observacao"] = (
                "Extração agendada; integração com `normalizacao.run_llm` entra na Fase 5."
            )
    except Exception as e:  # pragma: no cover
        with _LOCK:
            j = _JOBS[job_id]
            j.status = "erro"
            j.erro = str(e)
            j.concluido_em = _agora_iso()


def reset_para_testes() -> None:
    with _LOCK:
        _JOBS.clear()
