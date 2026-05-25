"""Resolução de presets de período em janelas (ano, mês).

`fact_ocorrencias` tem granularidade `(ano, mes)` — a coluna `data` original
é falsa, então toda janela temporal opera em meses. Os presets falam a língua
do gestor ("últimos 90 dias") mas a implementação trabalha em meses.

Cada janela é representada como `(ano_de, mes_de, ano_ate, mes_ate)` inclusiva
nos dois extremos. O "anchor" (mês mais recente nos dados) é resolvido uma vez
e reusado para a janela atual + janela anterior (Tarefa 1.2, variação mensal).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

# Presets aceitos pela query string `?periodo=...`.
PRESETS = ("ultimos_30d", "ultimos_90d", "ultimos_180d", "ano_vigente", "tudo")
PRESET_DEFAULT = "ultimos_90d"

# Mapa preset -> número de meses (None = comportamento especial).
_MESES_POR_PRESET = {
    "ultimos_30d": 1,
    "ultimos_90d": 3,
    "ultimos_180d": 6,
}


@dataclass(frozen=True)
class Janela:
    """Janela inclusiva em (ano, mês). `None` em ambos = sem filtro (preset `tudo`)."""

    ano_de: Optional[int]
    mes_de: Optional[int]
    ano_ate: Optional[int]
    mes_ate: Optional[int]

    @property
    def aberta(self) -> bool:
        """True quando não há filtro (preset `tudo`)."""
        return self.ano_de is None

    def como_periodo(self) -> Tuple[str, str]:
        """Devolve (de, ate) em formato 'YYYY-MM' para o contrato `Periodo`."""
        return (
            "%04d-%02d" % (self.ano_de, self.mes_de),
            "%04d-%02d" % (self.ano_ate, self.mes_ate),
        )


def _ancora() -> Optional[Tuple[int, int]]:
    """Mês mais recente em fact_ocorrencias, ou None se a tabela estiver vazia."""
    from .. import deps  # import tardio: pure tests não exigem duckdb

    row = deps.query_one(
        "SELECT MAX(ano * 100 + mes) AS k FROM read_csv_auto('%s') "
        "WHERE ano IS NOT NULL AND mes IS NOT NULL"
        % deps.silver("fact_ocorrencias.csv")
    )
    if not row or row.get("k") is None:
        return None
    k = int(row["k"])
    return k // 100, k % 100


def _amplitude_total() -> Optional[Tuple[int, int, int, int]]:
    """(ano_min, mes_min, ano_max, mes_max) cobrindo todo o histórico."""
    from .. import deps  # import tardio: pure tests não exigem duckdb

    row = deps.query_one(
        "SELECT MIN(ano * 100 + mes) AS lo, MAX(ano * 100 + mes) AS hi "
        "FROM read_csv_auto('%s') WHERE ano IS NOT NULL AND mes IS NOT NULL"
        % deps.silver("fact_ocorrencias.csv")
    )
    if not row or row.get("lo") is None:
        return None
    lo, hi = int(row["lo"]), int(row["hi"])
    return lo // 100, lo % 100, hi // 100, hi % 100


def _voltar_meses(ano: int, mes: int, n: int) -> Tuple[int, int]:
    """Recua `n` meses a partir de (ano, mes). n=1 e (2024, 3) -> (2024, 2)."""
    total = ano * 12 + (mes - 1) - n
    return total // 12, (total % 12) + 1


def _janela_de_meses(meses: int) -> Optional[Janela]:
    """Janela dos últimos `meses` meses contados a partir da âncora (inclusiva)."""
    anc = _ancora()
    if anc is None:
        return None
    ano_ate, mes_ate = anc
    ano_de, mes_de = _voltar_meses(ano_ate, mes_ate, meses - 1)
    return Janela(ano_de=ano_de, mes_de=mes_de, ano_ate=ano_ate, mes_ate=mes_ate)


def _janela_ano_vigente() -> Optional[Janela]:
    """De janeiro até o mês mais recente do ano mais recente nos dados."""
    anc = _ancora()
    if anc is None:
        return None
    ano_ate, mes_ate = anc
    return Janela(ano_de=ano_ate, mes_de=1, ano_ate=ano_ate, mes_ate=mes_ate)


def _janela_tudo() -> Janela:
    """Janela sem filtro (preset `tudo`) — preenche `de`/`ate` com a amplitude real."""
    amp = _amplitude_total()
    if amp is None:
        # Fallback duro: dados ausentes. Devolve janela aberta sem extremos.
        return Janela(None, None, None, None)
    ano_de, mes_de, ano_ate, mes_ate = amp
    return Janela(
        ano_de=ano_de, mes_de=mes_de, ano_ate=ano_ate, mes_ate=mes_ate
    )


def resolver(preset: Optional[str]) -> Tuple[str, Janela]:
    """Traduz o preset (ou nome ausente) numa janela concreta.

    Devolve `(preset_normalizado, janela)`. Levanta `ValueError` para preset
    desconhecido — o router converte em HTTP 400.
    """
    nome = (preset or PRESET_DEFAULT).strip().lower()
    if nome not in PRESETS:
        raise ValueError(
            "Preset de período inválido: %r (válidos: %s)"
            % (preset, ", ".join(PRESETS))
        )

    if nome == "tudo":
        return nome, _janela_tudo()
    if nome == "ano_vigente":
        j = _janela_ano_vigente() or _janela_tudo()
        return nome, j
    n = _MESES_POR_PRESET[nome]
    j = _janela_de_meses(n) or _janela_tudo()
    return nome, j


def janela_anterior(j: Janela) -> Optional[Janela]:
    """Janela imediatamente anterior, de mesmo comprimento. None se `j` for aberta."""
    if j.aberta or j.ano_de is None or j.ano_ate is None:
        return None
    comp = (j.ano_ate * 12 + j.mes_ate) - (j.ano_de * 12 + j.mes_de) + 1
    ano_ate_prev, mes_ate_prev = _voltar_meses(j.ano_de, j.mes_de, 1)
    ano_de_prev, mes_de_prev = _voltar_meses(ano_ate_prev, mes_ate_prev, comp - 1)
    return Janela(
        ano_de=ano_de_prev,
        mes_de=mes_de_prev,
        ano_ate=ano_ate_prev,
        mes_ate=mes_ate_prev,
    )


def variacao_pct(atual: int, anterior: int) -> Optional[float]:
    """Variação % entre dois totais. None quando o denominador é 0 (evita ∞)."""
    if anterior <= 0:
        return None
    return round((atual - anterior) / anterior * 100, 1)


def filtro_sql(j: Janela, alias: str = "") -> Tuple[str, list]:
    """SQL fragment + params para filtrar uma tabela `(ano, mes)` pela janela.

    `alias` permite qualificar (`"t."`) quando a tabela está em JOIN.
    Devolve `("", [])` quando a janela é aberta (sem filtro).
    """
    if j.aberta:
        return "", []
    a = "%sano" % alias
    m = "%smes" % alias
    sql = (
        " AND (%(a)s * 100 + %(m)s) BETWEEN ? AND ?"
        % {"a": a, "m": m}
    )
    return sql, [j.ano_de * 100 + j.mes_de, j.ano_ate * 100 + j.mes_ate]
