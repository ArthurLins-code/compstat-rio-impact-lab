"""Guardrails operacionais da IA (Tarefa 3.5).

Três proteções complementares:

1. **Rate limit** (token bucket por usuário/IP): protege contra abuso e
   loops do frontend. Default: burst 30, refill 1/segundo.
2. **Teto diário de custo USD**: soma custos do dia em `copilot_eventos`
   e bloqueia novas chamadas quando passa do teto. Default: USD 5/dia,
   configurável via `COMPSTAT_CUSTO_DIARIO_USD`.
3. **Kill switch**: env `COMPSTAT_AI_KILL_SWITCH=1` desativa a IA por
   completo — útil em incidente (ex.: chave vazada).

Sem login, "usuário" = IP de origem. Documentar que isso é provisório
até proximas_ideias.MD#3.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Dict


# ---------------------------------------------------------------------------
# Erros — caller decide o HTTP code (em geral 429 para rate, 503 para custo/kill).
# ---------------------------------------------------------------------------


class RateLimitError(RuntimeError):
    """Quota de requisições por segundo excedida."""


class OrcamentoExcedido(RuntimeError):
    """Teto diário de custo USD foi atingido."""


class IADesativada(RuntimeError):
    """Kill switch ligado — IA fora de operação por decisão operacional."""


# ---------------------------------------------------------------------------
# Token bucket por usuário (em RAM — não atravessa reinício; aceitável)
# ---------------------------------------------------------------------------


@dataclass
class _Bucket:
    tokens: float
    ultimo_refill: float


_BUCKETS: Dict[str, _Bucket] = {}
_LOCK = threading.Lock()


def _config_bucket():
    """Lê config a cada chamada — permite hot-tweak via env sem restart."""
    burst = int(os.environ.get("COMPSTAT_RATE_BURST", "30"))
    refill_por_seg = float(os.environ.get("COMPSTAT_RATE_REFILL", "1.0"))
    return burst, refill_por_seg


def consumir_token(usuario: str = "anonimo", custo: int = 1) -> None:
    """Tenta consumir `custo` tokens do bucket do usuário. Erro se faltar.

    `usuario` é arbitrário (IP, session_id, login quando existir). Não
    persiste — protege contra burst, não contra ataque sustentado lento.
    """
    burst, refill = _config_bucket()
    agora = time.monotonic()
    with _LOCK:
        b = _BUCKETS.get(usuario)
        if b is None:
            b = _Bucket(tokens=float(burst), ultimo_refill=agora)
            _BUCKETS[usuario] = b
        else:
            decorrido = agora - b.ultimo_refill
            b.tokens = min(float(burst), b.tokens + decorrido * refill)
            b.ultimo_refill = agora
        if b.tokens < custo:
            raise RateLimitError(
                "Rate limit excedido (%.1f token disponível, %d requerido)" % (b.tokens, custo)
            )
        b.tokens -= custo


def reset_buckets() -> None:
    """Limpa todos os buckets — usado em testes."""
    with _LOCK:
        _BUCKETS.clear()


# ---------------------------------------------------------------------------
# Teto diário de custo
# ---------------------------------------------------------------------------


def _teto_diario_usd() -> float:
    return float(os.environ.get("COMPSTAT_CUSTO_DIARIO_USD", "5.00"))


def custo_diario_atual_usd(usuario: str = None) -> float:
    """Soma custo USD do dia em copilot_eventos (delega a auditoria)."""
    try:
        from ..db import auditoria as _AUD
        return float(_AUD.resumo_diario(usuario).get("custo_usd", 0.0))
    except Exception:  # pragma: no cover - sem banco, sem teto
        return 0.0


def verificar_orcamento(usuario: str = None) -> None:
    """Levanta `OrcamentoExcedido` se o gasto do dia já passou do teto."""
    teto = _teto_diario_usd()
    gasto = custo_diario_atual_usd(usuario)
    if gasto >= teto:
        raise OrcamentoExcedido(
            "Teto diário de US$ %.2f atingido (gasto US$ %.2f). Retome amanhã ou aumente o teto."
            % (teto, gasto)
        )


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------


def kill_switch_ligado() -> bool:
    return os.environ.get("COMPSTAT_AI_KILL_SWITCH", "0").lower() in {"1", "true", "yes", "on"}


def verificar_kill_switch() -> None:
    if kill_switch_ligado():
        raise IADesativada(
            "IA está temporariamente desativada por decisão operacional "
            "(COMPSTAT_AI_KILL_SWITCH=1). Os dados e o mapa seguem disponíveis."
        )


# ---------------------------------------------------------------------------
# Verificação consolidada (chamar antes de qualquer call ao Claude)
# ---------------------------------------------------------------------------


def verificar_todos(usuario: str = "anonimo") -> None:
    """Executa as 3 verificações na ordem mais barata (RAM -> env -> DB)."""
    consumir_token(usuario)
    verificar_kill_switch()
    verificar_orcamento(usuario)
