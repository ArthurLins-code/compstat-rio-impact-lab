"""Testes da trilha de auditoria do copiloto."""
from __future__ import annotations

import os
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Cálculo de custo (puro)
# ---------------------------------------------------------------------------


def test_custo_sonnet_eh_calculado_em_decimal():
    from app.backend.db.auditoria import custo_estimado

    # 1M in @ 3 + 1M out @ 15 = 18 USD
    c = custo_estimado("claude-sonnet-4-6", 1_000_000, 1_000_000)
    assert c == Decimal("18.0000")


def test_custo_opus_mais_caro():
    from app.backend.db.auditoria import custo_estimado

    sonnet = custo_estimado("claude-sonnet-4-6", 100_000, 100_000)
    opus = custo_estimado("claude-opus-4-7", 100_000, 100_000)
    assert opus > sonnet


def test_custo_modelo_desconhecido_usa_fallback():
    from app.backend.db.auditoria import custo_estimado

    c = custo_estimado("modelo-inexistente", 10_000, 10_000)
    assert c == Decimal("0.1800")  # = 3*0.01 + 15*0.01


def test_hash_prompt_estavel_e_determinístico():
    from app.backend.db.auditoria import hash_prompt

    a = hash_prompt("texto qualquer")
    b = hash_prompt("texto qualquer")
    c = hash_prompt("texto diferente")
    assert a == b
    assert a != c
    assert len(a) == 64


# ---------------------------------------------------------------------------
# Integração: registrar + consolidar + resumo_diario
# ---------------------------------------------------------------------------


@pytest.fixture
def db_efemero(monkeypatch):
    pytest.importorskip("sqlalchemy")
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("COMPSTAT_DB_URL", "sqlite:///" + Path(path).as_posix())
    monkeypatch.setenv("COMPSTAT_PERSISTENT_STATE", "1")
    import importlib

    from app.backend import config as C
    from app.backend import db as DB

    importlib.reload(C)
    DB.reset_for_tests()
    DB.init_db()
    yield
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.mark.integration
def test_round_trip_registrar_consolidar(db_efemero):
    from app.backend.db import auditoria as A

    eid = A.registrar(area_id=20, secao_foco="dinamica_criminal", usuario="ip:127.0.0.1",
                      prompt_nome="copiloto")
    A.consolidar(
        eid,
        tokens_in=10_000,
        tokens_out=5_000,
        ferramentas=["consultar_ocorrencias", "consultar_fatores_urbanos"],
        resposta_resumo="resposta resumida",
        modelo="claude-sonnet-4-6",
    )

    resumo = A.resumo_diario()
    assert resumo["chamadas"] == 1
    assert resumo["tokens_in"] == 10_000
    assert resumo["tokens_out"] == 5_000
    # 10k in * 3/M + 5k out * 15/M = 0.03 + 0.075 = 0.105
    assert resumo["custo_usd"] == pytest.approx(0.105, rel=1e-3)


@pytest.mark.integration
def test_resumo_diario_filtra_por_usuario(db_efemero):
    from app.backend.db import auditoria as A

    e1 = A.registrar(area_id=20, usuario="ip:a")
    e2 = A.registrar(area_id=20, usuario="ip:b")
    A.consolidar(e1, tokens_in=1000, tokens_out=500, modelo="claude-sonnet-4-6")
    A.consolidar(e2, tokens_in=2000, tokens_out=500, modelo="claude-sonnet-4-6")

    assert A.resumo_diario("ip:a")["chamadas"] == 1
    assert A.resumo_diario("ip:b")["chamadas"] == 1
    assert A.resumo_diario()["chamadas"] == 2
