"""Testes do scheduler embutido e das tarefas operacionais."""
from __future__ import annotations

import threading
import time

import pytest

from app.backend.jobs import scheduler as S


def setup_function(_):
    S.reset_para_testes()


def teardown_function(_):
    S.parar()
    S.reset_para_testes()


def test_agendar_executa_periodicamente():
    contador = {"n": 0}
    evento = threading.Event()

    def func():
        contador["n"] += 1
        if contador["n"] >= 2:
            evento.set()

    S.agendar("ping", intervalo_s=1, func=func, rodar_agora=True)
    # Espera até 5s para evitar flakiness no Windows.
    evento.wait(timeout=5)
    assert contador["n"] >= 2


def test_status_reflete_execucoes():
    barreira = threading.Event()

    def func():
        barreira.set()

    S.agendar("ping", intervalo_s=10, func=func, rodar_agora=True)
    barreira.wait(timeout=3)
    time.sleep(0.1)  # janela pro callback consolidar status

    st = S.status()
    nome = [t["nome"] for t in st]
    assert "ping" in nome
    pings = [t for t in st if t["nome"] == "ping"][0]
    assert pings["execucoes"] >= 1
    assert pings["ultimaDuracaoMs"] is not None


def test_intervalo_minimo_eh_validado():
    with pytest.raises(ValueError):
        S.agendar("ping", intervalo_s=0, func=lambda: None)


def test_excecao_em_tarefa_nao_quebra_scheduler():
    counter = {"n": 0}
    evento = threading.Event()

    def func_bomba():
        counter["n"] += 1
        if counter["n"] >= 2:
            evento.set()
        raise RuntimeError("boom!")

    S.agendar("bomba", intervalo_s=1, func=func_bomba, rodar_agora=True)
    evento.wait(timeout=5)
    # Status registra o erro em `ultimoErro` mas a tarefa continua rodando.
    bomba = [t for t in S.status() if t["nome"] == "bomba"][0]
    assert bomba["execucoes"] >= 2
    assert bomba["ultimoErro"] is not None


# ---------------------------------------------------------------------------
# Tarefas: relatorio_frescor (puro)
# ---------------------------------------------------------------------------


def test_status_frescor_por_sla():
    from app.backend.jobs.tarefas import _status

    assert _status(10.0, 168) == "verde"
    assert _status(180.0, 168) == "ambar"  # 168 < 180 <= 168 * 1.5 = 252
    assert _status(300.0, 168) == "vermelho"
    assert _status(None, 168) == "vermelho"


def test_relatorio_frescor_estrutura():
    from app.backend.jobs.tarefas import relatorio_frescor

    r = relatorio_frescor()
    assert "datasets" in r
    assert "statusGeral" in r
    assert "computadoEm" in r
    assert r["statusGeral"] in {"verde", "ambar", "vermelho"}
    for d in r["datasets"]:
        assert set(d.keys()) >= {"nome", "idadeHoras", "slaHoras", "status", "presente"}
