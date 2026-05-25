"""Testes puros do mapeador 1746 -> fator urbano."""
from __future__ import annotations

from normalizacao.mapa_1746_para_fator import mapear


def test_iluminacao_com_subtipo_conhecido():
    cat, org = mapear("Iluminação Pública", "Lâmpada apagada")
    assert org == "Rio Luz"
    assert "iluminada" in cat.lower()


def test_iluminacao_subtipo_desconhecido_cai_no_default():
    # Subtipo inédito reaproveita o catch-all (tipo, "") -> evita perda de dado.
    result = mapear("Iluminação Pública", "Pisca-pisca natalino caído")
    assert result is not None
    assert result[1] == "Rio Luz"


def test_tipo_fora_do_catalogo_devolve_none():
    # 1746 tem tipos não-fator (saúde, animais soltos, etc.) — descartados.
    assert mapear("Atendimento de emergência veterinária", "qualquer") is None


def test_normalizacao_remove_acentos_e_caixa():
    a = mapear("PODA DE ÁRVORE", "")
    b = mapear("poda de arvore", "")
    assert a == b
    assert a is not None


def test_calcada_normalizada():
    cat, org = mapear("Manutenção de Calçada", "")
    assert org == "SECONSERVA"


def test_subtipo_none_eh_tratado_como_vazio():
    assert mapear("Poda de Árvore", None) is not None


def test_tipo_none_devolve_none():
    assert mapear(None, "qualquer") is None
