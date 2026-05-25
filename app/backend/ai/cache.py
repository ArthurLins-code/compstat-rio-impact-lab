"""Cache de respostas determinísticas da IA (Tarefa 3.3).

Aplica-se à geração de SEÇÕES (resumo executivo, dinâmica criminal, plano
de ação) — operações de saída determinística por desenho: mesmo brief +
mesmo prompt = mesma resposta. NÃO se aplica ao copiloto-chat, onde a
conversa é não-determinística por desenho.

Invalidação é natural: muda o `area_brief` (atualização do gold) → muda
o hash → cache miss → regeneração.

Sem `PERSISTENT_STATE`, todas as funções operam como no-op (sempre cache
miss). Mantém comportamento legado quando o flag está off.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any, Dict, Optional

from .. import config


def chave(area_brief: Dict[str, Any], secao: str, prompt_nome: str, prompt_versao: int) -> str:
    """sha256 estável de (brief canonicalizado, seção, prompt+versão)."""
    payload = {
        # Canonicaliza o brief: chaves ordenadas, sem espaços extras.
        "brief": json.dumps(area_brief, sort_keys=True, default=str, ensure_ascii=False),
        "secao": secao,
        "prompt_nome": prompt_nome,
        "prompt_versao": prompt_versao,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def obter(chave_hash: str) -> Optional[Dict[str, Any]]:
    """Devolve o conteúdo cacheado + incrementa `uso_count`/`ultimo_uso_em`.

    None = cache miss (ou flag desligado).
    """
    if not config.PERSISTENT_STATE:
        return None
    try:
        from ..db import get_session
        from ..db.models import RespostaCache
    except Exception:  # pragma: no cover
        return None
    with get_session() as s:
        r = s.get(RespostaCache, chave_hash)
        if r is None:
            return None
        r.uso_count = (r.uso_count or 0) + 1
        # `ultimo_uso_em` é atualizado pelo onupdate=_now via flush.
        s.flush()
        return r.conteudo


def salvar(
    chave_hash: str,
    *,
    area_id: int,
    secao: str,
    prompt_nome: str,
    prompt_versao: int,
    conteudo: Dict[str, Any],
    tokens_in: int = 0,
    tokens_out: int = 0,
    custo_usd: Optional[Decimal] = None,
) -> None:
    """Persiste a resposta com custos da chamada que a gerou."""
    if not config.PERSISTENT_STATE:
        return
    try:
        from ..db import get_session
        from ..db.models import RespostaCache
    except Exception:  # pragma: no cover
        return
    with get_session() as s:
        existente = s.get(RespostaCache, chave_hash)
        if existente is not None:
            # Hit numa chave que já existia — deixa estatística vir do `obter`.
            return
        s.add(
            RespostaCache(
                chave_hash=chave_hash,
                area_id=area_id,
                secao=secao,
                prompt_nome=prompt_nome,
                prompt_versao=prompt_versao,
                conteudo=conteudo,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                custo_usd=custo_usd,
            )
        )


def estatisticas() -> Dict[str, Any]:
    """Total + economia estimada (tokens/custo evitados pelos hits)."""
    if not config.PERSISTENT_STATE:
        return {"entradas": 0, "hits_estimados": 0, "custo_evitado_usd": 0.0}
    from ..db import get_session
    from ..db.models import RespostaCache

    with get_session() as s:
        rows = s.query(RespostaCache).all()
        hits = sum(max((r.uso_count or 1) - 1, 0) for r in rows)
        evit = float(sum((r.custo_usd or Decimal(0)) * max((r.uso_count or 1) - 1, 0) for r in rows))
        return {
            "entradas": len(rows),
            "hits_estimados": hits,
            "custo_evitado_usd": round(evit, 4),
        }
