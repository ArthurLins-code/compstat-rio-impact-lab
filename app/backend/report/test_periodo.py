"""Testes puros das funções aritméticas de `periodo.py`.

Os resolvers (`resolver`, `_janela_de_meses`) dependem do silver de
`fact_ocorrencias` (gitignored) — esses ficam marcados como integration.
"""
from __future__ import annotations

import pytest

from app.backend.report import periodo as P


def test_voltar_meses_dentro_do_mesmo_ano():
    assert P._voltar_meses(2024, 6, 3) == (2024, 3)


def test_voltar_meses_atravessa_o_ano():
    assert P._voltar_meses(2024, 2, 3) == (2023, 11)


def test_voltar_meses_um_ano_inteiro():
    assert P._voltar_meses(2024, 5, 12) == (2023, 5)


def test_voltar_meses_zero_e_no_op():
    assert P._voltar_meses(2024, 5, 0) == (2024, 5)


def test_janela_como_periodo_formata_com_padding():
    j = P.Janela(ano_de=2024, mes_de=3, ano_ate=2024, mes_ate=5)
    assert j.como_periodo() == ("2024-03", "2024-05")


def test_janela_aberta_quando_extremos_nulos():
    assert P.Janela(None, None, None, None).aberta is True


def test_janela_anterior_de_mesma_extensao():
    atual = P.Janela(ano_de=2024, mes_de=3, ano_ate=2024, mes_ate=5)  # 3 meses
    anterior = P.janela_anterior(atual)
    assert anterior == P.Janela(ano_de=2023, mes_de=12, ano_ate=2024, mes_ate=2)


def test_janela_anterior_de_janela_aberta_eh_none():
    assert P.janela_anterior(P.Janela(None, None, None, None)) is None


def test_filtro_sql_vazio_para_janela_aberta():
    sql, params = P.filtro_sql(P.Janela(None, None, None, None))
    assert sql == ""
    assert params == []


def test_filtro_sql_gera_between_inclusivo():
    j = P.Janela(ano_de=2024, mes_de=3, ano_ate=2024, mes_ate=5)
    sql, params = P.filtro_sql(j)
    assert "BETWEEN ? AND ?" in sql
    assert params == [202403, 202405]


def test_filtro_sql_aceita_alias():
    j = P.Janela(ano_de=2024, mes_de=1, ano_ate=2024, mes_ate=1)
    sql, _ = P.filtro_sql(j, alias="t.")
    assert "t.ano" in sql and "t.mes" in sql


def test_resolver_rejeita_preset_desconhecido():
    with pytest.raises(ValueError):
        P.resolver("ultimos_42d")


# ---------------------------------------------------------------------------
# Variação % (Tarefa 1.2)
# ---------------------------------------------------------------------------


def test_variacao_pct_aumento():
    assert P.variacao_pct(150, 100) == 50.0


def test_variacao_pct_queda():
    assert P.variacao_pct(80, 100) == -20.0


def test_variacao_pct_estavel():
    assert P.variacao_pct(100, 100) == 0.0


def test_variacao_pct_anterior_zerado_devolve_none():
    assert P.variacao_pct(10, 0) is None


def test_variacao_pct_arredondado_para_uma_casa():
    # 47/333 = 14.114114... -> 14.1
    assert P.variacao_pct(380, 333) == 14.1


# Integração: depende dos CSVs silver, marcado como `integration` e pulado no CI.
@pytest.mark.integration
def test_resolver_default_devolve_janela_concreta():
    nome, j = P.resolver(None)
    assert nome == P.PRESET_DEFAULT
    assert not j.aberta
    de, ate = j.como_periodo()
    assert len(de) == 7 and de[4] == "-"
    assert len(ate) == 7 and ate[4] == "-"
