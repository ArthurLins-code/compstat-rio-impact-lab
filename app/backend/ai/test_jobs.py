"""Testes de background jobs (reprocessar dinâmica)."""
from __future__ import annotations

from app.backend.ai import jobs as J


def setup_function(_):
    J.reset_para_testes()


def test_criar_job_atribui_uuid_e_estimativa():
    j = J.criar_job("reprocessar_dinamica", area_id=20)
    assert len(j.job_id) == 32
    assert j.status == "pendente"
    assert j.estimativa_custo_usd >= 0.0


def test_obter_job_inexistente_devolve_none():
    assert J.obter("nao-existe") is None


def test_rodar_marca_como_concluido():
    j = J.criar_job("reprocessar_dinamica", area_id=20)
    J.rodar_reprocessar_dinamica(j.job_id)
    final = J.obter(j.job_id)
    assert final["status"] == "concluido"
    assert final["concluido_em"] is not None
    assert "observacao" in final["detalhes"]


def test_estimar_custo_devolve_estrutura_consistente():
    est = J.estimar_custo(20)
    assert set(est.keys()) == {"n_relints", "custo_medio_usd_por_relint", "estimativa_total_usd"}
    assert est["estimativa_total_usd"] >= 0
