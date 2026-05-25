"""Testes do prompt registry."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


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
def test_seed_idempotente(db_efemero):
    from app.backend.db import prompts as P

    v1 = P.seed("copiloto", "texto v1")
    v2 = P.seed("copiloto", "texto v2 ignorado")  # já existe, ignora
    assert v1 == v2 == 1
    assert P.obter_ativo("copiloto") == (1, "texto v1")


@pytest.mark.integration
def test_promover_cria_v2_ativo_e_desativa_v1(db_efemero):
    from app.backend.db import prompts as P

    P.seed("copiloto", "v1")
    nova = P.promover("copiloto", "v2")
    assert nova == 2
    assert P.obter_ativo("copiloto") == (2, "v2")
    hist = P.historico("copiloto")
    assert [(h["versao"], h["ativo"]) for h in hist] == [(2, True), (1, False)]


@pytest.mark.integration
def test_rollback_reativa_versao_antiga(db_efemero):
    from app.backend.db import prompts as P

    P.seed("copiloto", "v1")
    P.promover("copiloto", "v2")
    P.promover("copiloto", "v3")
    P.rollback("copiloto", 1)
    assert P.obter_ativo("copiloto") == (1, "v1")


@pytest.mark.integration
def test_rollback_versao_inexistente_lookup_error(db_efemero):
    from app.backend.db import prompts as P

    P.seed("copiloto", "v1")
    with pytest.raises(LookupError):
        P.rollback("copiloto", 99)


@pytest.mark.integration
def test_runtime_get_usa_registry_quando_persistente(db_efemero):
    from app.backend.db import prompts as P

    # Sem nada no registry, runtime cai na constante (versão 0).
    from app.backend.ai import prompts_runtime as PR

    v_before, _ = PR.get("copiloto")
    assert v_before == 0

    # Depois de promover uma versão, runtime devolve a do registry.
    P.promover("copiloto", "PROMPT REWRITE V1")
    v_after, conteudo = PR.get("copiloto")
    assert v_after == 1
    assert conteudo == "PROMPT REWRITE V1"
