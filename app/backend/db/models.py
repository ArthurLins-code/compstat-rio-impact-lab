"""Modelos SQLAlchemy do CompStat Rio.

Catálogo:
- `SecaoOverride` — edição humana/IA de uma seção do relatório (Tarefa 2.2).
- `Acao` + `AcaoHistorico` — Plano de Ação com workflow auditável (2.3).
- `RelatorioVersao` — snapshot do relatório por versão (2.4).
- `CopilotEvento` — log estruturado de cada chamada do copiloto (2.5/Fase 3).

Decisões:
- Tipo `JSON` é o JSON nativo do SQLAlchemy 2.x (mapeia para `TEXT` no SQLite).
- `created_at`/`updated_at` em UTC, isoformat texto — facilita inspeção
  manual com `sqlite3 compstat.db`.
- `Numeric/Decimal` para custo financeiro do copiloto (precisão exata).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# 2.2 — Overrides de seção
# ---------------------------------------------------------------------------


class SecaoOverride(Base):
    __tablename__ = "secoes_overrides"

    area_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    secao: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    autor: Mapped[str] = mapped_column(String(16), nullable=False, default="humano")
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


# ---------------------------------------------------------------------------
# 2.3 — Plano de Ação + workflow
# ---------------------------------------------------------------------------


STATUS_VALIDOS = {
    "proposto",
    "atribuido",
    "em_andamento",
    "concluido",
    "nao_resolvido",
}


class Acao(Base):
    __tablename__ = "acoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    area_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    origem_acao_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    acao: Mapped[str] = mapped_column(String, nullable=False)
    responsavel: Mapped[str] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposto")
    prazo: Mapped["Date"] = mapped_column(Date, nullable=True)
    evidencia: Mapped[str] = mapped_column(String, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    atualizada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    historico: Mapped[list["AcaoHistorico"]] = relationship(
        "AcaoHistorico", back_populates="acao", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("area_id", "origem_acao_id", name="uq_acoes_area_origem"),
    )


class AcaoHistorico(Base):
    __tablename__ = "acoes_historico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    acao_id: Mapped[int] = mapped_column(
        ForeignKey("acoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    de_status: Mapped[str] = mapped_column(String(16), nullable=True)
    para_status: Mapped[str] = mapped_column(String(16), nullable=False)
    ator: Mapped[str] = mapped_column(String(64), nullable=False, default="anonimo")
    observacao: Mapped[str] = mapped_column(String, nullable=True)
    registrado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    acao: Mapped["Acao"] = relationship("Acao", back_populates="historico")


# ---------------------------------------------------------------------------
# 2.4 — Versões do relatório
# ---------------------------------------------------------------------------


class RelatorioVersao(Base):
    __tablename__ = "relatorios_versoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    area_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    origem: Mapped[str] = mapped_column(String(16), nullable=False, default="humano")
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    diff_texto: Mapped[str] = mapped_column(String, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("area_id", "versao", name="uq_relatorios_area_versao"),
    )


# ---------------------------------------------------------------------------
# Fase 3 (prepara aqui): eventos do copiloto
# ---------------------------------------------------------------------------


class RespostaCache(Base):
    """Cache de respostas geradas por seção (Tarefa 3.3).

    Chave determinística: hash de (area_brief, prompt_nome, prompt_versao,
    secao). Mesma área + mesmo brief + mesmo prompt = mesma resposta — não
    precisa chamar Claude de novo. `ultimo_uso_em` e `uso_count` ajudam a
    decidir TTL/expurgo na Fase 5.
    """

    __tablename__ = "respostas_cache"

    chave_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    area_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    secao: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_nome: Mapped[str] = mapped_column(String(64), nullable=True)
    prompt_versao: Mapped[int] = mapped_column(Integer, nullable=True)
    conteudo: Mapped[dict] = mapped_column(JSON, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=True)
    custo_usd: Mapped["Numeric"] = mapped_column(Numeric(10, 4), nullable=True)
    uso_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    ultimo_uso_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class Prompt(Base):
    """Versão de um prompt nomeado (Tarefa 3.2).

    Cada nome ('copiloto', 'sec_resumo_executivo', ...) tem N versões
    monotônicas. Apenas uma `ativo=1` por nome — quem promove desativa as
    anteriores. Nunca apaga: histórico é o que destrava A/B retroativo.
    """

    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    conteudo: Mapped[str] = mapped_column(String, nullable=False)
    ativo: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("nome", "versao", name="uq_prompts_nome_versao"),
    )


class CopilotEvento(Base):
    """Trilha de auditoria de uma interação com o copiloto.

    Apenas a estrutura nesta fase; o copiloto será instrumentado na Fase 3.
    Custos guardados em `Numeric(10,4)` para evitar arredondamento de float
    em relatórios de billing.
    """

    __tablename__ = "copilot_eventos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    area_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    secao_foco: Mapped[str] = mapped_column(String(64), nullable=True)
    usuario: Mapped[str] = mapped_column(String(64), nullable=False, default="anonimo")
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=True)
    prompt_nome: Mapped[str] = mapped_column(String(64), nullable=True)
    prompt_versao: Mapped[int] = mapped_column(Integer, nullable=True)
    ferramentas: Mapped[list] = mapped_column(JSON, nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=True)
    custo_usd: Mapped["Numeric"] = mapped_column(Numeric(10, 4), nullable=True)
    resposta_resumo: Mapped[str] = mapped_column(String, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    registrado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
