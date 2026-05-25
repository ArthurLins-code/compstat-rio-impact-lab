"""Testes do cache de respostas."""
from __future__ import annotations

import os
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Hash da chave (pura)
# ---------------------------------------------------------------------------


def test_chave_estavel_para_mesmo_brief():
    from app.backend.ai.cache import chave

    brief = {"area_fm_id": 20, "total_ocorrencias": 4011}
    a = chave(brief, "dinamica_criminal", "sec_dinamica_criminal", 3)
    b = chave(brief, "dinamica_criminal", "sec_dinamica_criminal", 3)
    assert a == b
    assert len(a) == 64


def test_chave_muda_quando_brief_muda():
    from app.backend.ai.cache import chave

    a = chave({"x": 1}, "s", "p", 1)
    b = chave({"x": 2}, "s", "p", 1)
    assert a != b


def test_chave_muda_quando_prompt_avanca_versao():
    from app.backend.ai.cache import chave

    a = chave({"x": 1}, "s", "p", 1)
    b = chave({"x": 1}, "s", "p", 2)
    assert a != b


def test_chave_invariante_a_ordem_de_chaves_do_brief():
    from app.backend.ai.cache import chave

    a = chave({"a": 1, "b": 2}, "s", "p", 1)
    b = chave({"b": 2, "a": 1}, "s", "p", 1)
    assert a == b


# ---------------------------------------------------------------------------
# Round-trip (integração)
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
def test_miss_depois_hit(db_efemero):
    from app.backend.ai import cache as Ca

    k = Ca.chave({"area": 20}, "dinamica_criminal", "sec_dinamica_criminal", 1)
    assert Ca.obter(k) is None

    Ca.salvar(
        k,
        area_id=20,
        secao="dinamica_criminal",
        prompt_nome="sec_dinamica_criminal",
        prompt_versao=1,
        conteudo={"text": "ok", "provenance": {"confidence": "alta"}},
        tokens_in=2000,
        tokens_out=500,
        custo_usd=Decimal("0.0135"),
    )
    assert Ca.obter(k) == {"text": "ok", "provenance": {"confidence": "alta"}}


@pytest.mark.integration
def test_estatisticas_acumulam_hits_e_custo_evitado(db_efemero):
    from app.backend.ai import cache as Ca

    k = Ca.chave({"area": 9}, "dinamica_criminal", "sec_dinamica_criminal", 1)
    Ca.salvar(
        k, area_id=9, secao="dinamica_criminal", prompt_nome="sec_dinamica_criminal",
        prompt_versao=1, conteudo={"text": "x"},
        tokens_in=1000, tokens_out=500, custo_usd=Decimal("0.0100"),
    )
    Ca.obter(k); Ca.obter(k); Ca.obter(k)  # 3 hits

    est = Ca.estatisticas()
    assert est["entradas"] == 1
    assert est["hits_estimados"] == 3
    # 3 hits * 0.0100 = 0.03 evitados.
    assert est["custo_evitado_usd"] == 0.03


def test_funcoes_no_op_sem_persistent_state(monkeypatch):
    monkeypatch.setenv("COMPSTAT_PERSISTENT_STATE", "0")
    import importlib

    from app.backend import config as C

    importlib.reload(C)
    from app.backend.ai import cache as Ca

    # Sem flag, todas as operações são no-op.
    Ca.salvar("k", area_id=20, secao="s", prompt_nome="p", prompt_versao=1, conteudo={})
    assert Ca.obter("k") is None
    assert Ca.estatisticas()["entradas"] == 0
