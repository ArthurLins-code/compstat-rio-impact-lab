"""Acesso read-only aos dados (DuckDB sobre os CSVs gold/silver).

Todas as funções aqui são somente leitura e devolvem estruturas Python simples
(dict / list[dict]). A camada de relatório/match consome estas funções; a Trilha 2
também as chama via `consultar(...)` (whitelist `ALLOWED_QUERIES`).

Guardrails:
- Nunca expõe `attributes_json` cru (PII do Disque Denúncia).
- Sem dado -> devolve None/[] (não inventa).
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

from .. import config, deps
from ..report.periodo import Janela, filtro_sql, janela_anterior, variacao_pct

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gold(name: str) -> str:
    """Trecho SQL read_csv_auto para um CSV da camada gold."""
    return "read_csv_auto('%s')" % deps.gold(name)


def _silver(name: str) -> str:
    return "read_csv_auto('%s')" % deps.silver(name)


def _parse_json(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _dinamica_path() -> str:
    return deps.silver("dinamica_extraida.csv")


def _dinamica_existe() -> bool:
    return os.path.exists(_dinamica_path())


# ---------------------------------------------------------------------------
# Listagem / brief
# ---------------------------------------------------------------------------


def listar_areas() -> List[dict]:
    """Uma linha por área FM: id, nome, total e ranking de ocorrências."""
    rows = deps.query(
        "SELECT area_fm_id, nome_area, total_ocorrencias, ranking_ocorrencias "
        "FROM %s ORDER BY ranking_ocorrencias" % _gold("area_brief.csv")
    )
    return [
        {
            "area_fm_id": int(r["area_fm_id"]),
            "nome_area": r["nome_area"],
            "total_ocorrencias": int(r["total_ocorrencias"]),
            "ranking_ocorrencias": int(r["ranking_ocorrencias"]),
        }
        for r in rows
    ]


# Rótulos de fatores_por_tipo que não representam um fator urbano acionável.
_FATOR_IGNORAR = {"Sem ocorrência"}


def _principal_fator(fatores: dict) -> Optional[str]:
    """Fator urbano de maior incidência, ignorando rótulos não acionáveis."""
    cand = {k: v for k, v in fatores.items() if k not in _FATOR_IGNORAR}
    if not cand:
        return None
    return max(cand, key=cand.get)


def resumo_areas() -> List[dict]:
    """Resumo por área FM para a página inicial, ordenado por urgência.

    Uma linha por área com os indicadores-chave do brief mais o principal fator
    urbano. As chaves já saem em camelCase (contrato AreaResumo).
    """
    rows = deps.query(
        "SELECT area_fm_id, nome_area, total_ocorrencias, ranking_ocorrencias, "
        "n_disque, n_cameras, n_psr_cpsr, pico_dia_semana, pico_hora, fatores_por_tipo "
        "FROM %s ORDER BY ranking_ocorrencias" % _gold("area_brief.csv")
    )
    return [
        {
            "areaId": int(r["area_fm_id"]),
            "nomeArea": r["nome_area"],
            "ranking": int(r["ranking_ocorrencias"]),
            "totalOcorrencias": int(r["total_ocorrencias"] or 0),
            "nDisque": int(r["n_disque"] or 0),
            "nCameras": int(r["n_cameras"] or 0),
            "nPsrCpsr": int(r["n_psr_cpsr"] or 0),
            "picoDiaSemana": r.get("pico_dia_semana") or "",
            "picoHora": int(r["pico_hora"]) if r.get("pico_hora") is not None else None,
            "principalFator": _principal_fator(_parse_json(r.get("fatores_por_tipo"), {})),
        }
        for r in rows
    ]


def area_brief_row(area_id: int) -> dict:
    """Linha bruta de area_brief para a área (campos JSON já desserializados)."""
    row = deps.query_one(
        "SELECT * FROM %s WHERE area_fm_id = ?" % _gold("area_brief.csv"),
        [area_id],
    )
    if row is None:
        return {}
    for col, default in [
        ("ocorrencias_por_tipo", {}),
        ("janelas_pico", []),
        ("fatores_por_tipo", {}),
        ("fatores_por_orgao", {}),
        ("faccoes_influencia", []),
        ("dinamica", {}),
        ("fontes_dinamica", []),
        ("avisos", []),
    ]:
        row[col] = _parse_json(row.get(col), default)
    return row


# ---------------------------------------------------------------------------
# Identificação e indicadores
# ---------------------------------------------------------------------------


def identificacao(area_id: int) -> dict:
    """Nome da área, facções de influência e principais bairros (se houver)."""
    brief = area_brief_row(area_id)
    nome_area = brief.get("nome_area", "")
    faccoes = [str(f) for f in brief.get("faccoes_influencia", []) if f]

    # bairro é quase sempre vazio em fact_ocorrencias; só inclui se de fato houver.
    bairros_rows = deps.query(
        "SELECT bairro, COUNT(*) AS n FROM %s "
        "WHERE area_fm_id = ? AND bairro IS NOT NULL AND TRIM(bairro) <> '' "
        "GROUP BY bairro ORDER BY n DESC LIMIT 5" % _silver("fact_ocorrencias.csv"),
        [area_id],
    )
    bairros = [r["bairro"] for r in bairros_rows]

    return {"nome_area": nome_area, "faccoes": faccoes, "bairros": bairros}


def _total_ocorrencias_janela(area_id: int, janela: Janela) -> int:
    """Conta ocorrências da área dentro da janela (ano, mês). 0 se janela vazia."""
    where_periodo, params_periodo = filtro_sql(janela)
    row = deps.query_one(
        "SELECT COUNT(*) AS n FROM %s WHERE area_fm_id = ?%s"
        % (_silver("fact_ocorrencias.csv"), where_periodo),
        [area_id, *params_periodo],
    )
    return int(row["n"]) if row and row.get("n") is not None else 0


def indicadores(area_id: int, janela: Optional[Janela] = None) -> dict:
    """Indicadores do período. Os dados só têm roubo (sem furto).

    `janela=None` ou `janela.aberta` mantém o comportamento legado (todo o
    histórico, vindo do `area_brief`, `variacaoPct=None`). Com janela definida
    `roubos`/`total` saem do silver filtrado e `variacaoPct` compara com a
    janela imediatamente anterior, de mesmo comprimento.
    """
    brief = area_brief_row(area_id)
    ranking = int(brief.get("ranking_ocorrencias") or 0)

    if janela is None or janela.aberta:
        total = int(brief.get("total_ocorrencias") or 0)
        variacao: Optional[float] = None
    else:
        total = _total_ocorrencias_janela(area_id, janela)
        anterior = janela_anterior(janela)
        variacao = (
            variacao_pct(total, _total_ocorrencias_janela(area_id, anterior))
            if anterior is not None
            else None
        )

    return {
        "roubos": total,
        "furtos": None,
        "total": total,
        "rankingEntreAreas": ranking,
        "variacaoPct": variacao,
    }


def distribuicao_tipo(
    area_id: int, janela: Optional[Janela] = None
) -> List[dict]:
    """Ocorrências por tipo, ordenadas (rank 1 = maior).

    Sem janela usa o agregado gold (rápido). Com janela recompõe a partir
    de `fact_ocorrencias` filtrado por (ano, mês).
    """
    if janela is None or janela.aberta:
        rows = deps.query(
            "SELECT category, qtd FROM %s WHERE area_fm_id = ? "
            "ORDER BY qtd DESC" % _gold("gold_ocorrencias_tipo.csv"),
            [area_id],
        )
    else:
        where_periodo, params_periodo = filtro_sql(janela)
        rows = deps.query(
            "SELECT category, COUNT(*) AS qtd FROM %s "
            "WHERE area_fm_id = ?%s "
            "GROUP BY category ORDER BY qtd DESC"
            % (_silver("fact_ocorrencias.csv"), where_periodo),
            [area_id, *params_periodo],
        )
    return [
        {"tipo": r["category"], "qtd": int(r["qtd"]), "rank": i + 1}
        for i, r in enumerate(rows)
    ]


# ---------------------------------------------------------------------------
# Matriz temporal (7 x 24)
# ---------------------------------------------------------------------------


def matriz_temporal(area_id: int, janela: Optional[Janela] = None) -> dict:
    """Matriz 7x24 (dias na ordem WEEKDAY_PT) + dia/hora críticos e cobertura.

    Sem janela usa o agregado gold (rápido). Com janela reagrega a partir
    do silver filtrado por (ano, mês).
    """
    dias = list(config.WEEKDAY_PT)
    dia_idx = {d: i for i, d in enumerate(dias)}
    matrix = [[0 for _ in range(24)] for _ in range(7)]

    if janela is None or janela.aberta:
        rows = deps.query(
            "SELECT dia_semana, hora, qtd FROM %s WHERE area_fm_id = ?"
            % _gold("gold_temporal.csv"),
            [area_id],
        )
    else:
        where_periodo, params_periodo = filtro_sql(janela)
        rows = deps.query(
            "SELECT dia_semana, hora, COUNT(*) AS qtd FROM %s "
            "WHERE area_fm_id = ?%s "
            "GROUP BY dia_semana, hora"
            % (_silver("fact_ocorrencias.csv"), where_periodo),
            [area_id, *params_periodo],
        )
    for r in rows:
        d = r["dia_semana"]
        h = r["hora"]
        if d not in dia_idx or h is None:
            continue
        h = int(h)
        if 0 <= h <= 23:
            matrix[dia_idx[d]][h] += int(r["qtd"] or 0)

    # dia/hora crítica = célula de maior qtd
    dia_critico = ""
    hora_critica: Optional[int] = None
    maior = -1
    for di in range(7):
        for h in range(24):
            if matrix[di][h] > maior:
                maior = matrix[di][h]
                dia_critico = dias[di]
                hora_critica = h
    if maior <= 0:
        dia_critico = ""
        hora_critica = None

    # período predominante a partir da hora crítica
    periodo = ""
    if hora_critica is not None:
        if 6 <= hora_critica < 12:
            periodo = "Manhã"
        elif 12 <= hora_critica < 18:
            periodo = "Tarde"
        elif 18 <= hora_critica < 24:
            periodo = "Noite"
        else:
            periodo = "Madrugada"

    # cobertura: total de registros (fact_ocorrencias) e quantos sem hora,
    # respeitando a mesma janela usada na matriz acima.
    where_cov, params_cov = filtro_sql(janela) if janela is not None else ("", [])
    cov = deps.query_one(
        "SELECT COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE hora IS NULL) AS sem_hora "
        "FROM %s WHERE area_fm_id = ?%s"
        % (_silver("fact_ocorrencias.csv"), where_cov),
        [area_id, *params_cov],
    ) or {"total": 0, "sem_hora": 0}

    return {
        "matrix": matrix,
        "dias": dias,
        "periodoPredominante": periodo,
        "diaCritico": dia_critico,
        "horaCritica": hora_critica,
        "coverage": {
            "totalRegistros": int(cov["total"] or 0),
            "semHora": int(cov["sem_hora"] or 0),
        },
    }


# ---------------------------------------------------------------------------
# Fatores urbanos por órgão
# ---------------------------------------------------------------------------


def fatores_por_orgao(area_id: int) -> List[dict]:
    """Fatores urbanos (causa removível) por tipo e órgão responsável."""
    rows = deps.query(
        "SELECT category, orgao_responsavel, qtd FROM %s WHERE area_fm_id = ? "
        "ORDER BY qtd DESC" % _gold("gold_fatores_orgao.csv"),
        [area_id],
    )
    return [
        {
            "category": r["category"],
            "orgao_responsavel": r["orgao_responsavel"],
            "qtd": int(r["qtd"] or 0),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Câmeras
# ---------------------------------------------------------------------------


def cameras_info(area_id: int) -> dict:
    """Total de câmeras na área."""
    row = deps.query_one(
        "SELECT COUNT(*) AS total FROM %s WHERE area_fm_id = ?"
        % _silver("fact_cameras.csv"),
        [area_id],
    )
    return {"total": int(row["total"]) if row else 0}


# ---------------------------------------------------------------------------
# Dinâmica criminal estruturada (RELINT / Disque) — degrade se arquivo ausente
# ---------------------------------------------------------------------------


def dinamica_estruturada(area_id: int) -> Optional[List[dict]]:
    """Afirmações estruturadas de dinâmica criminal da área.

    Devolve None se silver/dinamica_extraida.csv não existir (degrade).
    Filtra `declarado_ausente` (afirmações de ausência não viram indício).
    """
    if not _dinamica_existe():
        return None
    rows = deps.query(
        "SELECT sub_local, doc_id, fonte_tipo, campo, valor, trecho_fonte, "
        "confianca, declarado_ausente "
        "FROM %s WHERE area_fm_id = ? AND COALESCE(declarado_ausente, FALSE) = FALSE "
        "ORDER BY CASE confianca WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END"
        % _silver("dinamica_extraida.csv"),
        [area_id],
    )
    return [
        {
            "sub_local": r["sub_local"],
            "doc_id": r["doc_id"],
            "fonte_tipo": r["fonte_tipo"],
            "campo": r["campo"],
            "valor": r["valor"],
            "trecho_fonte": r["trecho_fonte"],
            "confianca": r["confianca"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Disque Denúncia — amostra SEM PII (só tema/category)
# ---------------------------------------------------------------------------


def disque_amostra(area_id: int, limite: int = 25) -> List[dict]:
    """Temas das denúncias agregados por categoria. NÃO expõe texto cru (PII)."""
    rows = deps.query(
        "SELECT category AS tema, COUNT(*) AS qtd FROM %s WHERE area_fm_id = ? "
        "GROUP BY category ORDER BY qtd DESC LIMIT ?"
        % _silver("fact_disque_denuncia.csv"),
        [area_id, limite],
    )
    return [
        {"tema": r["tema"], "category": r["tema"], "qtd": int(r["qtd"] or 0)}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Geometrias (pontos) — só com lat/lon não nulos
# ---------------------------------------------------------------------------


def ocorrencias_geo(area_id: int) -> List[dict]:
    rows = deps.query(
        "SELECT lat, lon, category, hora, dia_semana FROM %s "
        "WHERE area_fm_id = ? AND lat IS NOT NULL AND lon IS NOT NULL"
        % _silver("fact_ocorrencias.csv"),
        [area_id],
    )
    return [
        {
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "category": r["category"],
            "hora": int(r["hora"]) if r["hora"] is not None else None,
            "dia_semana": r["dia_semana"],
        }
        for r in rows
    ]


def cameras_geo(area_id: int) -> List[dict]:
    rows = deps.query(
        "SELECT lat, lon, category FROM %s "
        "WHERE area_fm_id = ? AND lat IS NOT NULL AND lon IS NOT NULL"
        % _silver("fact_cameras.csv"),
        [area_id],
    )
    return [
        {"lat": float(r["lat"]), "lon": float(r["lon"]), "category": r["category"]}
        for r in rows
    ]


def fatores_geo(area_id: int) -> List[dict]:
    rows = deps.query(
        "SELECT lat, lon, category, orgao_responsavel FROM %s "
        "WHERE area_fm_id = ? AND lat IS NOT NULL AND lon IS NOT NULL"
        % _silver("fact_fatores_urbanos.csv"),
        [area_id],
    )
    return [
        {
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "category": r["category"],
            "orgao": r["orgao_responsavel"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Domínio territorial (facção) por área
# ---------------------------------------------------------------------------


def dominio_da_area(area_id: int) -> List[str]:
    """Facções/ORCRIM com domínio declarado na área (de dim_dominio_territorial).

    area_fm_ids vem como número (ex.: 20.0) ou string; comparamos por inteiro.
    """
    rows = deps.query(
        "SELECT DISTINCT dominio_orcrim FROM %s "
        "WHERE dominio_orcrim IS NOT NULL AND area_fm_ids IS NOT NULL "
        "AND TRY_CAST(area_fm_ids AS INTEGER) = ?"
        % _silver("dim_dominio_territorial.csv"),
        [area_id],
    )
    return [r["dominio_orcrim"] for r in rows if r["dominio_orcrim"]]


# ---------------------------------------------------------------------------
# Whitelist de consultas (Trilha 2 chama via consultar())
# ---------------------------------------------------------------------------

ALLOWED_QUERIES: Dict[str, Callable[..., Any]] = {
    "indicadores": indicadores,
    "distribuicao_tipo": distribuicao_tipo,
    "matriz_temporal": matriz_temporal,
    "fatores_por_orgao": fatores_por_orgao,
    "dinamica_estruturada": dinamica_estruturada,
}


def consultar(nome: str, area_id: int, **kw) -> Any:
    """Roteia para uma consulta da whitelist. ValueError se `nome` inválido."""
    fn = ALLOWED_QUERIES.get(nome)
    if fn is None:
        raise ValueError(
            "Consulta não permitida: %r (permitidas: %s)"
            % (nome, ", ".join(sorted(ALLOWED_QUERIES)))
        )
    return fn(area_id, **kw)
