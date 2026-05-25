"""Testes dos guardrails de IA (rate limit + custo + kill switch)."""
from __future__ import annotations

import time

import pytest

from app.backend.ai import guardrails as G


def setup_function(_):
    G.reset_buckets()


# ---------------------------------------------------------------------------
# Token bucket
# ---------------------------------------------------------------------------


def test_consumir_dentro_do_burst_inicial(monkeypatch):
    monkeypatch.setenv("COMPSTAT_RATE_BURST", "5")
    G.reset_buckets()
    # 5 consumos consecutivos cabem no burst.
    for _ in range(5):
        G.consumir_token("ip:test")


def test_excede_burst_levanta_rate_limit(monkeypatch):
    monkeypatch.setenv("COMPSTAT_RATE_BURST", "3")
    monkeypatch.setenv("COMPSTAT_RATE_REFILL", "0.001")  # refill desprezível
    G.reset_buckets()
    for _ in range(3):
        G.consumir_token("ip:abuse")
    with pytest.raises(G.RateLimitError):
        G.consumir_token("ip:abuse")


def test_buckets_separados_por_usuario(monkeypatch):
    monkeypatch.setenv("COMPSTAT_RATE_BURST", "1")
    monkeypatch.setenv("COMPSTAT_RATE_REFILL", "0.001")
    G.reset_buckets()
    G.consumir_token("ip:a")
    G.consumir_token("ip:b")  # não compete com 'a'
    with pytest.raises(G.RateLimitError):
        G.consumir_token("ip:a")


def test_refill_recupera_tokens(monkeypatch):
    monkeypatch.setenv("COMPSTAT_RATE_BURST", "2")
    monkeypatch.setenv("COMPSTAT_RATE_REFILL", "100.0")  # refill agressivo
    G.reset_buckets()
    G.consumir_token("ip:r")
    G.consumir_token("ip:r")
    time.sleep(0.05)  # 50ms * 100 = 5 tokens recuperados — folga ampla p/ Windows
    G.consumir_token("ip:r")  # deve passar


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------


def test_kill_switch_desligado_por_default(monkeypatch):
    monkeypatch.delenv("COMPSTAT_AI_KILL_SWITCH", raising=False)
    assert G.kill_switch_ligado() is False
    G.verificar_kill_switch()  # não levanta


def test_kill_switch_ligado_bloqueia(monkeypatch):
    monkeypatch.setenv("COMPSTAT_AI_KILL_SWITCH", "1")
    assert G.kill_switch_ligado() is True
    with pytest.raises(G.IADesativada):
        G.verificar_kill_switch()


def test_kill_switch_aceita_variantes(monkeypatch):
    for val in ("true", "YES", "on", "On"):
        monkeypatch.setenv("COMPSTAT_AI_KILL_SWITCH", val)
        assert G.kill_switch_ligado() is True


# ---------------------------------------------------------------------------
# Teto de custo (sem DB -> 0 gasto -> não bloqueia)
# ---------------------------------------------------------------------------


def test_orcamento_sem_gasto_nao_bloqueia(monkeypatch):
    monkeypatch.setenv("COMPSTAT_CUSTO_DIARIO_USD", "5.00")
    # Sem PERSISTENT_STATE, custo_diario_atual_usd devolve 0 e não bloqueia.
    monkeypatch.delenv("COMPSTAT_PERSISTENT_STATE", raising=False)
    G.verificar_orcamento()


def test_teto_padrao():
    # Documenta o default (5 USD) — anti-regressão silenciosa.
    assert G._teto_diario_usd() == 5.00
