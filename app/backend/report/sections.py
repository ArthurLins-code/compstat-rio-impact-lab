"""Montagem das seções determinísticas do relatório (com proveniência).

Cada seção devolve um model Pydantic já com `Provenance` (linguagem de negócio,
confiança alta, `sources` com `recordCount`, `technicalDetail` curto). Os blocos de
IA nascem como placeholders `status="nao_gerado"` com `blockId` estável — a Trilha
de IA os preenche depois.
"""
from __future__ import annotations

from typing import List, Optional

from ..data import duck as D
from . import models as M
from .periodo import Janela

# ---------------------------------------------------------------------------
# Perguntas norteadoras (resumo executivo)
# ---------------------------------------------------------------------------

_PERGUNTAS = [
    ("q1", "Locais de maior incidência coincidem com a rota da FM?"),
    ("q2", "Horário de maior incidência coincide com o QMD (horário de cobertura)?"),
    ("q3", "A dinâmica criminal coincide com o modelo de emprego da FM?"),
    ("q4", "Os fatores relevantes estão sendo resolvidos pelos órgãos?"),
]

_EFETIVO_CAMPOS = [
    "Nº de Agentes por Turno",
    "Locais de Cobertura",
    "Horário de Cobertura",
    "Dias de Cobertura",
    "Modalidade de Emprego",
]


def _block(secao: str, area_id: int) -> M.AiBlock:
    """Placeholder de bloco de IA (não gerado), com blockId estável."""
    return M.AiBlock(
        blockId="%s:%d" % (secao, area_id),
        sectionId=secao,
        status="nao_gerado",
    )


# ---------------------------------------------------------------------------
# Identificação
# ---------------------------------------------------------------------------


def sec_identificacao(area_id: int) -> M.Identificacao:
    ident = D.identificacao(area_id)
    prov = M.Provenance(
        rationale=(
            "Nome da área e influência de grupos criminosos vêm do cadastro das "
            "áreas FM e do mapeamento de domínio territorial."
        ),
        confidence="alta",
        sources=[
            M.SourceCitation(
                kind="dominio",
                label="grupos com influência mapeada na área",
                recordCount=len(ident.get("faccoes", [])),
            )
        ],
        warnings=[],
        technicalDetail="área FM identificada por area_fm_id no cadastro",
    )
    return M.Identificacao(
        areaFM=area_id,
        nomeArea=ident.get("nome_area", ""),
        bairros=ident.get("bairros", []),
        aisp="",
        dp="",
        bpm="",
        baseFM="",
        subprefeitura="",
        influenciaGrupoCriminoso=ident.get("faccoes", []),
        trechosCriticos=None,
        provenance=prov,
    )


# ---------------------------------------------------------------------------
# Ocorrências
# ---------------------------------------------------------------------------


def sec_ocorrencias(area_id: int, janela: Optional[Janela] = None) -> M.Ocorrencias:
    ind = D.indicadores(area_id, janela)
    dist = D.distribuicao_tipo(area_id, janela)
    indicadores = M.IndicadoresPeriodo(
        roubos=ind["roubos"],
        furtos=ind["furtos"],
        total=ind["total"],
        rankingEntreAreas=ind["rankingEntreAreas"],
        variacaoPct=ind["variacaoPct"],
    )
    distribuicao = [
        M.DistribuicaoTipo(tipo=d["tipo"], qtd=d["qtd"], rank=d["rank"]) for d in dist
    ]
    prov = M.Provenance(
        rationale=(
            "Total de ocorrências e distribuição por tipo somam todos os registros "
            "de roubo da área no período. Os dados cobrem apenas roubo (sem furto)."
        ),
        confidence="alta",
        sources=[
            M.SourceCitation(
                kind="quantitativo",
                label="ocorrências de roubo na área",
                recordCount=ind["total"],
            )
        ],
        warnings=["Os dados cobrem apenas roubo (sem furto)."],
        technicalDetail="ocorrências da área filtradas por area_fm_id",
    )
    return M.Ocorrencias(
        indicadores=indicadores, distribuicao=distribuicao, provenance=prov
    )


# ---------------------------------------------------------------------------
# Fatores de incidência (por órgão)
# ---------------------------------------------------------------------------


def sec_fatores(area_id: int) -> M.FatoresIncidencia:
    fatores = D.fatores_por_orgao(area_id)
    total = sum(f["qtd"] for f in fatores)
    rows = [
        M.FatorOrgao(
            fator=f["category"],
            descricao="",
            orgaoResponsavel=f["orgao_responsavel"],
            qtd=f["qtd"],
        )
        for f in fatores
    ]
    prov = M.Provenance(
        rationale=(
            "Fatores urbanos são condições do ambiente (iluminação, vegetação, "
            "comércio irregular) que favorecem o crime; cada um é atribuído ao "
            "órgão responsável por resolvê-lo."
        ),
        confidence="alta",
        sources=[
            M.SourceCitation(
                kind="fator",
                label="fatores urbanos mapeados na área",
                recordCount=total,
            )
        ],
        warnings=[],
        technicalDetail="fatores urbanos da área filtrados por area_fm_id",
    )
    return M.FatoresIncidencia(rows=rows, provenance=prov)


# ---------------------------------------------------------------------------
# Câmeras
# ---------------------------------------------------------------------------


def sec_cameras(area_id: int) -> M.Cameras:
    info = D.cameras_info(area_id)
    prov = M.Provenance(
        rationale="Total de câmeras de videomonitoramento instaladas na área.",
        confidence="alta",
        sources=[
            M.SourceCitation(
                kind="camera",
                label="câmeras na área",
                recordCount=info["total"],
            )
        ],
        warnings=[],
        technicalDetail="câmeras da área filtradas por area_fm_id",
    )
    return M.Cameras(total=info["total"], provenance=prov)


# ---------------------------------------------------------------------------
# Matriz temporal
# ---------------------------------------------------------------------------


def sec_temporal(area_id: int, janela: Optional[Janela] = None) -> M.TemporalMatrix:
    mt = D.matriz_temporal(area_id, janela)
    return M.TemporalMatrix(
        matrix=mt["matrix"],
        dias=mt["dias"],
        periodoPredominante=mt["periodoPredominante"],
        diaCritico=mt["diaCritico"],
        horaCritica=mt["horaCritica"],
        coverage=mt["coverage"],
    )


# ---------------------------------------------------------------------------
# Placeholders de IA
# ---------------------------------------------------------------------------


def sec_resumo_executivo(area_id: int) -> List[M.PerguntaNorteadora]:
    return [
        M.PerguntaNorteadora(
            id=qid,
            pergunta=texto,
            diagnostico=_block("resumoExecutivo:%s" % qid, area_id),
        )
        for qid, texto in _PERGUNTAS
    ]


def sec_temporal_resumo(area_id: int) -> M.AiBlock:
    return _block("temporalResumo", area_id)


def sec_dinamica_criminal(area_id: int) -> M.AiBlock:
    return _block("dinamicaCriminal", area_id)


def sec_efetivo_fm(area_id: int) -> List[M.EfetivoRow]:
    return [
        M.EfetivoRow(blockId="efetivoFM:%d:%s" % (area_id, campo), campo=campo)
        for campo in _EFETIVO_CAMPOS
    ]


def sec_plano_acao(area_id: int) -> List[M.AcaoRow]:
    """Plano de ação derivado dos fatores urbanos (uma ação por órgão responsável)."""
    fatores = D.fatores_por_orgao(area_id)
    por_orgao: dict = {}
    for f in fatores:
        org = f.get("orgao_responsavel") or "Órgão não identificado"
        por_orgao.setdefault(org, []).append((f["category"], f["qtd"]))

    acoes: List[M.AcaoRow] = []
    for i, (org, itens) in enumerate(
        sorted(por_orgao.items(), key=lambda kv: -sum(q for _, q in kv[1]))
    ):
        principais = ", ".join(c for c, _ in sorted(itens, key=lambda x: -x[1])[:2])
        acoes.append(
            M.AcaoRow(
                id="%d-a%d" % (area_id, i + 1),
                acao="Tratar fatores urbanos: %s" % principais,
                responsavel=org,
                prazo="",
                status="proposto",
                provenance=M.Provenance(
                    rationale=(
                        "Ação proposta a partir dos fatores urbanos da área sob "
                        "responsabilidade de %s." % org
                    ),
                    confidence="alta",
                    sources=[
                        M.SourceCitation(
                            kind="fator",
                            label="fatores sob responsabilidade de %s" % org,
                            recordCount=sum(q for _, q in itens),
                        )
                    ],
                ),
            )
        )
    return acoes
