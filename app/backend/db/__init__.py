"""Camada de persistência (SQLAlchemy + SQLite por default).

Engine + session ficam aqui. Os modelos vivem em `models.py`. As operações
de domínio (overrides, ações, versões) ficam em módulos próprios — este
pacote só expõe `get_session()` e `init_db()`.

Quando `config.PERSISTENT_STATE=False`, o módulo continua importável (não
abre conexão), mas nada chama `init_db()` — o resto do app continua em
memória, mantendo o comportamento legado.
"""
from __future__ import annotations

import contextlib
from typing import Iterator, Optional

from .. import config

_engine = None
_SessionLocal = None


def _make_engine():
    """Cria o engine SQLAlchemy. Import tardio: sqlalchemy só carrega quando ligamos o flag."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # `check_same_thread=False`: o uvicorn troca de thread no SSE/streaming; a
    # conexão SQLite por padrão é thread-local. Como nossas escritas são curtas
    # e usamos uma sessão por requisição, é seguro.
    engine = create_engine(
        config.DB_URL,
        future=True,
        connect_args=(
            {"check_same_thread": False} if config.DB_URL.startswith("sqlite") else {}
        ),
    )
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def _ensure_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine, _SessionLocal = _make_engine()
    return _engine, _SessionLocal


def init_db() -> None:
    """Cria as tabelas se faltarem. Chamado no startup quando PERSISTENT_STATE."""
    from .models import Base

    engine, _ = _ensure_engine()
    Base.metadata.create_all(engine)


@contextlib.contextmanager
def get_session() -> Iterator["object"]:
    """Sessão SQLAlchemy escopada à operação. Commit no sucesso, rollback no erro."""
    _, SessionLocal = _ensure_engine()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_for_tests() -> None:
    """Limpa o engine cacheado — testes podem trocar `DB_URL` entre rodadas."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
