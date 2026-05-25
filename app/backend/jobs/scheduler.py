"""Scheduler embutido (Tarefa 5.1).

Sem dependência externa (APScheduler/Celery/Prefect entram quando o
volume justificar). Hoje a operação é "1-2 cargas/dia" — uma thread
daemon com `threading.Timer` resolve sem broker.

Cada tarefa agendada roda na thread do scheduler (não no event loop do
uvicorn), então pode bloquear sem afetar requisições. Exceções são
logadas, nunca propagadas — uma tarefa quebrada não derruba as outras.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

_LOG = logging.getLogger("compstat.jobs")


@dataclass
class TarefaAgendada:
    nome: str
    intervalo_s: float
    func: Callable[[], None]
    timer: Optional[threading.Timer] = None
    ultima_exec_em: Optional[str] = None
    ultima_duracao_ms: Optional[int] = None
    ultimo_erro: Optional[str] = None
    execucoes: int = 0


_TAREFAS: Dict[str, TarefaAgendada] = {}
_LOCK = threading.Lock()
_PARADO = False


def _agora() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _executar(t: TarefaAgendada) -> None:
    """Roda uma tarefa, mede tempo, loga JSON e reagenda."""
    if _PARADO:
        return
    inicio = time.perf_counter()
    erro: Optional[str] = None
    try:
        t.func()
    except Exception as e:
        erro = repr(e)
    finally:
        dur_ms = int((time.perf_counter() - inicio) * 1000)
        with _LOCK:
            t.ultima_exec_em = _agora()
            t.ultima_duracao_ms = dur_ms
            t.ultimo_erro = erro
            t.execucoes += 1
        try:
            _LOG.info(
                json.dumps(
                    {
                        "ts": _agora(),
                        "level": "ERROR" if erro else "INFO",
                        "logger": "compstat.jobs",
                        "tarefa": t.nome,
                        "duracao_ms": dur_ms,
                        "erro": erro,
                        "execucoes": t.execucoes,
                    },
                    ensure_ascii=False,
                )
            )
        except Exception:  # pragma: no cover
            pass
        _reagendar(t)


def _reagendar(t: TarefaAgendada) -> None:
    if _PARADO:
        return
    timer = threading.Timer(t.intervalo_s, _executar, args=(t,))
    timer.daemon = True
    with _LOCK:
        t.timer = timer
    timer.start()


def agendar(
    nome: str,
    intervalo_s: float,
    func: Callable[[], None],
    rodar_agora: bool = False,
) -> None:
    """Registra uma tarefa para rodar a cada `intervalo_s` segundos.

    `rodar_agora=True` dispara uma execução imediata em thread separada
    além do ciclo recorrente.
    """
    if intervalo_s < 1:
        raise ValueError("intervalo_s mínimo é 1 (proteção contra busy loop)")
    t = TarefaAgendada(nome=nome, intervalo_s=intervalo_s, func=func)
    with _LOCK:
        # Substitui silenciosamente se já existir (reload em dev).
        antiga = _TAREFAS.get(nome)
        if antiga and antiga.timer:
            antiga.timer.cancel()
        _TAREFAS[nome] = t
    if rodar_agora:
        threading.Thread(target=_executar, args=(t,), daemon=True).start()
    else:
        _reagendar(t)


def parar() -> None:
    """Cancela todos os timers — chamado no shutdown."""
    global _PARADO
    _PARADO = True
    with _LOCK:
        for t in _TAREFAS.values():
            if t.timer:
                t.timer.cancel()


def status() -> List[Dict]:
    """Snapshot das tarefas para diagnóstico (consumido por /api/health/data)."""
    with _LOCK:
        return [
            {
                "nome": t.nome,
                "intervaloSegundos": t.intervalo_s,
                "execucoes": t.execucoes,
                "ultimaExecEm": t.ultima_exec_em,
                "ultimaDuracaoMs": t.ultima_duracao_ms,
                "ultimoErro": t.ultimo_erro,
            }
            for t in _TAREFAS.values()
        ]


def reset_para_testes() -> None:
    global _PARADO
    _PARADO = False
    with _LOCK:
        for t in _TAREFAS.values():
            if t.timer:
                t.timer.cancel()
        _TAREFAS.clear()
