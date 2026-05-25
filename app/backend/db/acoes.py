"""Plano de Ação com workflow auditável (Tarefa 2.3).

Mantém a máquina de estados (`TRANSICOES_VALIDAS`) e a operação CRUD em
torno das tabelas `acoes` + `acoes_historico`. O router (`routers/acoes.py`)
é só uma camada fina HTTP.

Modelo de estados:
    proposto       -> atribuido | nao_resolvido
    atribuido      -> em_andamento | nao_resolvido
    em_andamento   -> concluido | nao_resolvido
    concluido      -> em_andamento          (reabertura)
    nao_resolvido  -> atribuido             (reabertura)
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from . import get_session
from .models import STATUS_VALIDOS, Acao, AcaoHistorico

# Edges válidos do grafo de estados. Tupla origem -> conjunto de destinos.
TRANSICOES_VALIDAS: Dict[str, set] = {
    "proposto": {"atribuido", "nao_resolvido"},
    "atribuido": {"em_andamento", "nao_resolvido"},
    "em_andamento": {"concluido", "nao_resolvido"},
    "concluido": {"em_andamento"},
    "nao_resolvido": {"atribuido"},
}

SLA_PADRAO = timedelta(days=90)


class TransicaoInvalida(ValueError):
    """Tentativa de mover ação para um status não permitido pela máquina de estados."""


class AcaoNaoEncontrada(LookupError):
    pass


# ---------------------------------------------------------------------------
# Operações
# ---------------------------------------------------------------------------


def _serialize(a: Acao, com_historico: bool = False) -> Dict[str, Any]:
    """Devolve a ação como dict serializável (datetimes em ISO)."""
    base = {
        "id": a.id,
        "areaId": a.area_id,
        "origemAcaoId": a.origem_acao_id,
        "acao": a.acao,
        "responsavel": a.responsavel,
        "status": a.status,
        "prazo": a.prazo.isoformat() if a.prazo else None,
        "evidencia": a.evidencia,
        "criadaEm": a.criada_em.isoformat() if a.criada_em else None,
        "atualizadaEm": a.atualizada_em.isoformat() if a.atualizada_em else None,
    }
    if com_historico:
        base["historico"] = [_serialize_hist(h) for h in sorted(a.historico, key=lambda h: h.registrado_em)]
    return base


def _serialize_hist(h: AcaoHistorico) -> Dict[str, Any]:
    return {
        "id": h.id,
        "deStatus": h.de_status,
        "paraStatus": h.para_status,
        "ator": h.ator,
        "observacao": h.observacao,
        "registradoEm": h.registrado_em.isoformat() if h.registrado_em else None,
    }


def listar(area_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista as ações da área, opcionalmente filtradas por status."""
    with get_session() as s:
        q = s.query(Acao).filter(Acao.area_id == area_id)
        if status:
            q = q.filter(Acao.status == status)
        return [_serialize(a) for a in q.order_by(Acao.criada_em.desc()).all()]


def criar(
    area_id: int,
    acao: str,
    responsavel: Optional[str] = None,
    origem_acao_id: Optional[str] = None,
    prazo: Optional[date] = None,
    ator: str = "anonimo",
) -> Dict[str, Any]:
    """Cria ação no status `proposto` e registra transição inicial no histórico."""
    with get_session() as s:
        # Idempotência: se já existir (area_id, origem_acao_id), devolve a atual.
        if origem_acao_id is not None:
            existente = (
                s.query(Acao)
                .filter(Acao.area_id == area_id, Acao.origem_acao_id == origem_acao_id)
                .one_or_none()
            )
            if existente is not None:
                return _serialize(existente)
        a = Acao(
            area_id=area_id,
            acao=acao,
            responsavel=responsavel,
            origem_acao_id=origem_acao_id,
            status="proposto",
            prazo=prazo or (date.today() + SLA_PADRAO),
        )
        s.add(a)
        s.flush()
        s.add(
            AcaoHistorico(
                acao_id=a.id, de_status=None, para_status="proposto", ator=ator
            )
        )
        s.flush()
        return _serialize(a)


def atualizar(
    acao_id: int,
    *,
    status: Optional[str] = None,
    responsavel: Optional[str] = None,
    prazo: Optional[date] = None,
    evidencia: Optional[str] = None,
    observacao: Optional[str] = None,
    ator: str = "anonimo",
) -> Dict[str, Any]:
    """Atualiza campos da ação. Mudança de status valida transição + grava histórico."""
    with get_session() as s:
        a = s.get(Acao, acao_id)
        if a is None:
            raise AcaoNaoEncontrada("Ação %d não existe." % acao_id)

        if status is not None and status != a.status:
            if status not in STATUS_VALIDOS:
                raise TransicaoInvalida(
                    "Status %r inválido (válidos: %s)" % (status, ", ".join(sorted(STATUS_VALIDOS)))
                )
            permitidos = TRANSICOES_VALIDAS.get(a.status, set())
            if status not in permitidos:
                raise TransicaoInvalida(
                    "Transição %s -> %s não permitida (permitidos a partir de %s: %s)"
                    % (a.status, status, a.status, ", ".join(sorted(permitidos)) or "—")
                )
            s.add(
                AcaoHistorico(
                    acao_id=a.id,
                    de_status=a.status,
                    para_status=status,
                    ator=ator,
                    observacao=observacao,
                )
            )
            a.status = status

        if responsavel is not None:
            a.responsavel = responsavel
        if prazo is not None:
            a.prazo = prazo
        if evidencia is not None:
            a.evidencia = evidencia

        s.flush()
        return _serialize(a)


def historico(acao_id: int) -> List[Dict[str, Any]]:
    """Devolve o histórico da ação (ordenado cronologicamente)."""
    with get_session() as s:
        a = s.get(Acao, acao_id)
        if a is None:
            raise AcaoNaoEncontrada("Ação %d não existe." % acao_id)
        return [_serialize_hist(h) for h in sorted(a.historico, key=lambda h: h.registrado_em)]


def seed_da_area(area_id: int, propostas: List[Dict[str, Any]], ator: str = "sistema") -> int:
    """Popula `acoes` com as propostas (idempotente via origem_acao_id).

    `propostas` é o que `sec_plano_acao` devolve hoje (lista de AcaoRow dicts).
    Retorna a contagem de ações novas (já existentes são puladas).
    """
    novas = 0
    for p in propostas:
        origem = str(p.get("id") or "")
        if not origem:
            continue
        antes = listar(area_id, status=None)
        criar(
            area_id=area_id,
            acao=p.get("acao") or "",
            responsavel=p.get("responsavel"),
            origem_acao_id=origem,
            ator=ator,
        )
        depois = listar(area_id, status=None)
        if len(depois) > len(antes):
            novas += 1
    return novas
