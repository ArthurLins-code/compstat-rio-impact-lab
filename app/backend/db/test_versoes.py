"""Testes do versionamento de relatório."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Diff resumido (pura)
# ---------------------------------------------------------------------------


def test_diff_versao_inicial():
    from app.backend.db.versoes import _resumo_diff

    assert _resumo_diff({"a": 1}, None) == "versão inicial"


def test_diff_sem_mudanca():
    from app.backend.db.versoes import _resumo_diff

    assert _resumo_diff({"a": 1, "b": 2}, {"a": 1, "b": 2}) == "sem mudança estrutural"


def test_diff_lista_secoes_mudadas_ordenadas():
    from app.backend.db.versoes import _resumo_diff

    novo = {"dinamicaCriminal": "x", "planoAcao": "y", "fatores": "z"}
    ant = {"dinamicaCriminal": "x", "planoAcao": "old", "fatores": "z"}
    assert _resumo_diff(novo, ant) == "planoAcao"


def test_diff_chave_nova():
    from app.backend.db.versoes import _resumo_diff

    assert _resumo_diff({"a": 1, "b": 2}, {"a": 1}) == "b"


# ---------------------------------------------------------------------------
# Integração (snapshot + listar + taxa de edição)
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
def test_versoes_monotonicas(db_efemero):
    from app.backend.db import versoes as V

    v1 = V.snapshot(20, {"x": 1}, origem="humano")
    v2 = V.snapshot(20, {"x": 2}, origem="ia")
    v3 = V.snapshot(20, {"x": 3}, origem="humano")
    assert (v1["versao"], v2["versao"], v3["versao"]) == (1, 2, 3)


@pytest.mark.integration
def test_listar_devolve_em_ordem_decrescente(db_efemero):
    from app.backend.db import versoes as V

    V.snapshot(20, {"x": 1}, "humano")
    V.snapshot(20, {"x": 2}, "ia")
    lista = V.listar(20)
    assert [v["versao"] for v in lista] == [2, 1]


@pytest.mark.integration
def test_taxa_de_edicao_humana(db_efemero):
    from app.backend.db import versoes as V

    assert V.taxa_de_edicao_humana(20) is None  # vazia
    V.snapshot(20, {"x": 1}, "humano")
    V.snapshot(20, {"x": 2}, "ia")
    V.snapshot(20, {"x": 3}, "humano")
    V.snapshot(20, {"x": 4}, "humano")
    assert V.taxa_de_edicao_humana(20) == 75.0


@pytest.mark.integration
def test_obter_devolve_snapshot_completo(db_efemero):
    from app.backend.db import versoes as V

    V.snapshot(20, {"dinamicaCriminal": {"text": "hello"}}, "humano")
    snap = V.obter(20, 1)
    assert snap is not None
    assert snap["snapshot"]["dinamicaCriminal"]["text"] == "hello"
    assert V.obter(20, 99) is None
