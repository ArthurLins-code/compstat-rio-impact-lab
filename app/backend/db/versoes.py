"""Histórico de versões do relatório (Tarefa 2.4).

Cada edição de seção gera um snapshot do relatório completo com a `origem`
(`humano`|`ia`) e um resumo legível do que mudou. O diff serve à Fase 3:
"taxa de aceitação humana das sugestões da IA" alimenta o A/B de prompts.

Decisões:
- Snapshot completo (não delta): SQLite aguenta, e simplifica restauração.
- `diff_texto` é resumo curto ("seção X mudou ~120 chars"), não diff
  estrutural — a UI usa para timeline; quem quiser comparar campo a campo
  pega os dois snapshots e faz o diff client-side.
- Versão é monotônica por área (1, 2, 3, ...). Não há rollback nesta fase.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import get_session
from .models import RelatorioVersao


def _resumo_diff(novo: dict, anterior: Optional[dict]) -> str:
    """Resumo legível das seções mudadas entre dois snapshots.

    Anterior == None: primeira versão da área. Caso contrário compara as
    seções top-level e devolve uma lista curta tipo
    `"dinamicaCriminal, planoAcao"`.
    """
    if anterior is None:
        return "versão inicial"
    mudadas: List[str] = []
    chaves = set(novo.keys()) | set(anterior.keys())
    for k in sorted(chaves):
        if novo.get(k) != anterior.get(k):
            mudadas.append(k)
    if not mudadas:
        return "sem mudança estrutural"
    return ", ".join(mudadas)


def proxima_versao(area_id: int) -> int:
    """Próximo número de versão (1-based) para a área."""
    with get_session() as s:
        ultima = (
            s.query(RelatorioVersao)
            .filter(RelatorioVersao.area_id == area_id)
            .order_by(RelatorioVersao.versao.desc())
            .first()
        )
        return (ultima.versao + 1) if ultima is not None else 1


def snapshot(area_id: int, payload: dict, origem: str = "humano") -> Dict[str, Any]:
    """Grava nova versão do relatório com diff resumido vs versão anterior."""
    with get_session() as s:
        ultima = (
            s.query(RelatorioVersao)
            .filter(RelatorioVersao.area_id == area_id)
            .order_by(RelatorioVersao.versao.desc())
            .first()
        )
        versao = (ultima.versao + 1) if ultima is not None else 1
        diff = _resumo_diff(payload, ultima.snapshot if ultima else None)
        v = RelatorioVersao(
            area_id=area_id,
            versao=versao,
            origem=origem,
            snapshot=payload,
            diff_texto=diff,
        )
        s.add(v)
        s.flush()
        return {
            "id": v.id,
            "areaId": area_id,
            "versao": versao,
            "origem": origem,
            "diffTexto": diff,
            "criadoEm": v.criado_em.isoformat() if v.criado_em else None,
        }


def listar(area_id: int) -> List[Dict[str, Any]]:
    """Metadados (sem snapshot, para payload enxuto)."""
    with get_session() as s:
        rows = (
            s.query(RelatorioVersao)
            .filter(RelatorioVersao.area_id == area_id)
            .order_by(RelatorioVersao.versao.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "areaId": r.area_id,
                "versao": r.versao,
                "origem": r.origem,
                "diffTexto": r.diff_texto,
                "criadoEm": r.criado_em.isoformat() if r.criado_em else None,
            }
            for r in rows
        ]


def taxa_de_edicao_humana(area_id: int) -> Optional[float]:
    """% de versões 'humano' sobre o total — sinal para promoção de prompt (Fase 3).

    None quando não há versões (área nunca editada).
    """
    with get_session() as s:
        q = s.query(RelatorioVersao).filter(RelatorioVersao.area_id == area_id)
        total = q.count()
        if total == 0:
            return None
        humanas = q.filter(RelatorioVersao.origem == "humano").count()
        return round(humanas / total * 100, 1)


def obter(area_id: int, versao: int) -> Optional[Dict[str, Any]]:
    """Devolve o snapshot completo de uma versão específica."""
    with get_session() as s:
        r = (
            s.query(RelatorioVersao)
            .filter(RelatorioVersao.area_id == area_id, RelatorioVersao.versao == versao)
            .one_or_none()
        )
        if r is None:
            return None
        return {
            "id": r.id,
            "areaId": r.area_id,
            "versao": r.versao,
            "origem": r.origem,
            "diffTexto": r.diff_texto,
            "snapshot": r.snapshot,
            "criadoEm": r.criado_em.isoformat() if r.criado_em else None,
        }
