"""Registry de prompts versionados (Tarefa 3.2).

Cada nome (`copiloto`, `sec_resumo_executivo`, ...) tem versões
incrementais. `obter_ativo(nome)` traz a versão em uso; `promover` cria
v+1 e marca como ativa, desativando a anterior. `seed` é idempotente
(escreve v1 se não houver nada).

O `prompts_runtime.get(nome)` consulta isto quando PERSISTENT_STATE
está ligado; sem flag (ou sem entrada), cai no constante do módulo —
mantendo o app utilizável offline.
"""
from __future__ import annotations

from typing import Optional, Tuple

from . import get_session
from .models import Prompt


def obter_ativo(nome: str) -> Optional[Tuple[int, str]]:
    """Devolve `(versao, conteudo)` da versão ativa, ou None se não houver."""
    with get_session() as s:
        p = (
            s.query(Prompt)
            .filter(Prompt.nome == nome, Prompt.ativo == 1)
            .order_by(Prompt.versao.desc())
            .first()
        )
        return (p.versao, p.conteudo) if p else None


def historico(nome: str) -> list:
    """Lista metadados de todas as versões (mais recente primeiro)."""
    with get_session() as s:
        rows = (
            s.query(Prompt)
            .filter(Prompt.nome == nome)
            .order_by(Prompt.versao.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "nome": r.nome,
                "versao": r.versao,
                "ativo": bool(r.ativo),
                "criadoEm": r.criado_em.isoformat() if r.criado_em else None,
            }
            for r in rows
        ]


def seed(nome: str, conteudo: str) -> int:
    """Garante que existe pelo menos a v1 ativa para o nome. Devolve a versão atual."""
    atual = obter_ativo(nome)
    if atual is not None:
        return atual[0]
    with get_session() as s:
        s.add(Prompt(nome=nome, versao=1, conteudo=conteudo, ativo=1))
    return 1


def promover(nome: str, conteudo: str) -> int:
    """Cria v+1 e marca como ativa; desativa as anteriores. Devolve a nova versão."""
    with get_session() as s:
        ultima = (
            s.query(Prompt)
            .filter(Prompt.nome == nome)
            .order_by(Prompt.versao.desc())
            .first()
        )
        # Desativa todas as anteriores.
        s.query(Prompt).filter(Prompt.nome == nome, Prompt.ativo == 1).update(
            {Prompt.ativo: 0}, synchronize_session=False
        )
        nova_versao = (ultima.versao + 1) if ultima else 1
        s.add(Prompt(nome=nome, versao=nova_versao, conteudo=conteudo, ativo=1))
    return nova_versao


def rollback(nome: str, para_versao: int) -> None:
    """Reativa uma versão antiga, desativando as demais (sem deletar)."""
    with get_session() as s:
        alvo = (
            s.query(Prompt)
            .filter(Prompt.nome == nome, Prompt.versao == para_versao)
            .one_or_none()
        )
        if alvo is None:
            raise LookupError("Versão %s/%d não existe." % (nome, para_versao))
        s.query(Prompt).filter(Prompt.nome == nome).update(
            {Prompt.ativo: 0}, synchronize_session=False
        )
        alvo.ativo = 1
