"""Testes do workflow de ações.

Os testes que tocam SQLAlchemy ficam `integration`: o CI puro (sem
dependência de banco) só roda os testes da máquina de estados. O
smoke completo roda quando há `sqlalchemy` instalado.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Máquina de estados (pura — não precisa de banco)
# ---------------------------------------------------------------------------


def test_grafo_de_transicoes_tem_todos_os_status_como_origem():
    """Toda configuração de status válido tem pelo menos uma transição saindo
    (ou aparece como destino) — garante que não há "estado morto"."""
    from app.backend.db.acoes import TRANSICOES_VALIDAS
    from app.backend.db.models import STATUS_VALIDOS

    origens = set(TRANSICOES_VALIDAS.keys())
    destinos = {d for ds in TRANSICOES_VALIDAS.values() for d in ds}
    assert STATUS_VALIDOS.issubset(origens | destinos)


def test_proposto_nao_pula_para_concluido():
    """Anti-regressão: pular `proposto -> concluido` ignora o workflow."""
    from app.backend.db.acoes import TRANSICOES_VALIDAS

    assert "concluido" not in TRANSICOES_VALIDAS["proposto"]


def test_nao_resolvido_pode_ser_reaberto():
    from app.backend.db.acoes import TRANSICOES_VALIDAS

    assert "atribuido" in TRANSICOES_VALIDAS["nao_resolvido"]


def test_concluido_pode_voltar_para_em_andamento():
    from app.backend.db.acoes import TRANSICOES_VALIDAS

    assert "em_andamento" in TRANSICOES_VALIDAS["concluido"]


def test_status_nao_vai_para_ele_mesmo():
    from app.backend.db.acoes import TRANSICOES_VALIDAS

    for origem, destinos in TRANSICOES_VALIDAS.items():
        assert origem not in destinos, "%s -> %s seria no-op suspeito" % (origem, origem)


# ---------------------------------------------------------------------------
# Integração (round-trip no SQLite efêmero)
# ---------------------------------------------------------------------------


@pytest.fixture
def db_efemero(monkeypatch):
    sa = pytest.importorskip("sqlalchemy")  # noqa: F841
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("COMPSTAT_DB_URL", "sqlite:///" + Path(path).as_posix())
    monkeypatch.setenv("COMPSTAT_PERSISTENT_STATE", "1")
    # Recarrega config + reseta engine cacheado.
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
def test_ciclo_completo_de_uma_acao(db_efemero):
    from app.backend.db import acoes as A

    a = A.criar(area_id=20, acao="Trocar lâmpadas da Rua X", responsavel="Rio Luz",
                origem_acao_id="seed-1")
    assert a["status"] == "proposto"
    assert a["prazo"] is not None

    a = A.atualizar(a["id"], status="atribuido", ator="gestor")
    assert a["status"] == "atribuido"

    a = A.atualizar(a["id"], status="em_andamento", ator="gestor")
    a = A.atualizar(a["id"], status="concluido", evidencia="OS-1234", ator="gestor")
    assert a["status"] == "concluido"
    assert a["evidencia"] == "OS-1234"

    hist = A.historico(a["id"])
    # 4 entradas: inicial (None -> proposto) + 3 transições.
    assert [(h["deStatus"], h["paraStatus"]) for h in hist] == [
        (None, "proposto"),
        ("proposto", "atribuido"),
        ("atribuido", "em_andamento"),
        ("em_andamento", "concluido"),
    ]


@pytest.mark.integration
def test_rejeita_transicao_invalida(db_efemero):
    from app.backend.db import acoes as A

    a = A.criar(area_id=19, acao="Poda", responsavel="COMLURB", origem_acao_id="x")
    with pytest.raises(A.TransicaoInvalida):
        A.atualizar(a["id"], status="concluido")  # pula etapas


@pytest.mark.integration
def test_seed_idempotente(db_efemero):
    from app.backend.db import acoes as A

    propostas = [
        {"id": "20-a1", "acao": "Limpar via", "responsavel": "COMLURB"},
        {"id": "20-a2", "acao": "Trocar lâmpada", "responsavel": "Rio Luz"},
    ]
    n1 = A.seed_da_area(20, propostas)
    n2 = A.seed_da_area(20, propostas)
    assert n1 == 2
    assert n2 == 0  # já existiam — nenhuma nova
    assert len(A.listar(20)) == 2
