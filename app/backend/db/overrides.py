"""Persistência dos overrides de seção do relatório.

`salvar(area_id, secao, payload, autor)` faz upsert; `carregar(area_id)`
devolve `{secao: payload}` para o assembler aplicar. Estas funções só são
chamadas quando `config.PERSISTENT_STATE=True` — o assembler escolhe o
backend (memória ou SQLite) no momento da operação.
"""
from __future__ import annotations

from typing import Any, Dict

from . import get_session
from .models import SecaoOverride


def salvar(area_id: int, secao: str, payload: dict, autor: str = "humano") -> None:
    """Upsert de override. `autor` distingue edição humana vs sugestão da IA."""
    with get_session() as s:
        existente = s.get(SecaoOverride, (area_id, secao))
        if existente is None:
            s.add(SecaoOverride(area_id=area_id, secao=secao, payload=payload, autor=autor))
        else:
            existente.payload = payload
            existente.autor = autor


def carregar(area_id: int) -> Dict[str, Any]:
    """Devolve `{secao: payload}` com todos os overrides da área."""
    with get_session() as s:
        rows = s.query(SecaoOverride).filter(SecaoOverride.area_id == area_id).all()
        return {r.secao: r.payload for r in rows}


def limpar(area_id: int) -> int:
    """Apaga todos os overrides da área. Devolve a contagem removida (útil em testes)."""
    with get_session() as s:
        n = (
            s.query(SecaoOverride)
            .filter(SecaoOverride.area_id == area_id)
            .delete(synchronize_session=False)
        )
        return n
