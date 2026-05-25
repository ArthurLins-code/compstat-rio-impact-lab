"""Trilha de auditoria de cada interação com Claude (Tarefa 3.1).

Duas fases: `registrar` cria a linha com o que sabemos no início (área,
seção foco, usuário, prompt usado) e devolve `evento_id`; `consolidar`
preenche tokens/custo/resumo no fim.

Custo é calculado a partir dos tokens e da tabela de preços do modelo
(`TABELA_CUSTOS_USD`) — atualizar quando a Anthropic ajustar preços.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any, Dict, List, Optional

from . import get_session
from .models import CopilotEvento

# USD por 1M tokens (input, output). Fonte: anthropic.com/pricing — manter alinhado.
TABELA_CUSTOS_USD = {
    "claude-opus-4-7": (15.00, 75.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    # fallback conservador (Sonnet-like)
    "default": (3.00, 15.00),
}


def custo_estimado(model: str, tokens_in: int, tokens_out: int) -> Decimal:
    """USD pela chamada (Decimal, precisão de 4 casas)."""
    in_per_m, out_per_m = TABELA_CUSTOS_USD.get(model, TABELA_CUSTOS_USD["default"])
    return Decimal(
        str(round(tokens_in / 1_000_000 * in_per_m + tokens_out / 1_000_000 * out_per_m, 4))
    )


def hash_prompt(texto: str) -> str:
    """sha256(prompt) — identifica versão exata mesmo se ainda não estiver no registry."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def registrar(
    area_id: int,
    secao_foco: Optional[str] = None,
    usuario: str = "anonimo",
    prompt_nome: Optional[str] = None,
    prompt_versao: Optional[int] = None,
    prompt_hash_str: Optional[str] = None,
) -> int:
    """Cria evento sem custos/tokens (preenche no `consolidar`). Devolve evento_id."""
    with get_session() as s:
        e = CopilotEvento(
            area_id=area_id,
            secao_foco=secao_foco,
            usuario=usuario,
            prompt_nome=prompt_nome,
            prompt_versao=prompt_versao,
            prompt_hash=prompt_hash_str,
        )
        s.add(e)
        s.flush()
        return e.id


def consolidar(
    evento_id: int,
    *,
    tokens_in: int = 0,
    tokens_out: int = 0,
    custo_usd: Optional[Decimal] = None,
    ferramentas: Optional[List[str]] = None,
    resposta_resumo: Optional[str] = None,
    cache_hit: bool = False,
    modelo: Optional[str] = None,
) -> None:
    """Atualiza o evento com tokens/custo/ferramentas/resumo ao final da chamada.

    `custo_usd=None` + `modelo` fornecido -> calculado pelo `custo_estimado`.
    """
    if custo_usd is None and modelo is not None:
        custo_usd = custo_estimado(modelo, tokens_in, tokens_out)

    with get_session() as s:
        e = s.get(CopilotEvento, evento_id)
        if e is None:
            return
        e.tokens_in = int(tokens_in or 0)
        e.tokens_out = int(tokens_out or 0)
        if custo_usd is not None:
            e.custo_usd = custo_usd
        if ferramentas is not None:
            e.ferramentas = ferramentas
        if resposta_resumo is not None:
            e.resposta_resumo = resposta_resumo[:500]  # cap defensivo
        e.cache_hit = 1 if cache_hit else 0


def resumo_diario(usuario: Optional[str] = None) -> Dict[str, Any]:
    """Total de chamadas, tokens e custo no dia (UTC). Usado pelo guardrail de custo."""
    from datetime import datetime, time, timezone

    inicio = datetime.combine(datetime.now(tz=timezone.utc).date(), time.min, tzinfo=timezone.utc)
    with get_session() as s:
        q = s.query(CopilotEvento).filter(CopilotEvento.registrado_em >= inicio)
        if usuario is not None:
            q = q.filter(CopilotEvento.usuario == usuario)
        eventos = q.all()
        return {
            "chamadas": len(eventos),
            "tokens_in": sum(e.tokens_in or 0 for e in eventos),
            "tokens_out": sum(e.tokens_out or 0 for e in eventos),
            "custo_usd": float(sum((e.custo_usd or Decimal(0)) for e in eventos)),
            "cache_hits": sum(1 for e in eventos if e.cache_hit),
        }
