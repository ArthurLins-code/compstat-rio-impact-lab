"""Testes do match: score() (pura) e compute_match() (geometria).

Os testes de compute_match() são marcados como `integration` porque dependem
dos CSVs em dados_normalizados/silver/ (gitignored). No CI rodamos só os
testes puros (`pytest -m "not integration"`); o teste de integração é
executado localmente quando os dados estão presentes.
"""
from __future__ import annotations

import pytest

from app.backend.match import score as scoremod

# Imports pesados (duckdb, models pydantic) ficam dentro dos testes de
# integração para que `pytest -m "not integration"` no CI não exija a
# instalação dessas deps só para validar as funções puras de score().

CAMADAS_VALIDAS = {"mancha", "fator", "dinamica", "lacuna_camera"}


# ---------------------------------------------------------------------------
# score() — função pura, valores conhecidos
# ---------------------------------------------------------------------------


def test_score_maximo():
    assert scoremod.score(1.0, True, True, True) == 10.0


def test_score_minimo():
    assert scoremod.score(0.0, False, False, False) == 0.0


def test_score_satura_em_10():
    # 5*1 + 2 + 1.5 + 1.5 = 10, mas mesmo extrapolando não passa de 10.
    assert scoremod.score(2.0, True, True, True) == 10.0


def test_score_componentes():
    # só densidade 0.5 -> 2.5
    assert scoremod.score(0.5, False, False, False) == 2.5
    # densidade 0 + fator -> 2.0
    assert scoremod.score(0.0, True, False, False) == 2.0
    # densidade 0 + dinamica -> 1.5
    assert scoremod.score(0.0, False, True, False) == 1.5
    # densidade 0 + lacuna -> 1.5
    assert scoremod.score(0.0, False, False, True) == 1.5


def test_score_no_intervalo():
    for dens in (0.0, 0.3, 0.7, 1.0):
        for tf in (True, False):
            for td in (True, False):
                for lc in (True, False):
                    v = scoremod.score(dens, tf, td, lc)
                    assert 0.0 <= v <= 10.0


# ---------------------------------------------------------------------------
# compute_match() — área real (20)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_compute_match_area20():
    from app.backend.match.engine import compute_match
    from app.backend.report import models as M

    r = compute_match(20)
    assert isinstance(r, M.MatchResult)
    assert r.areaId == 20
    assert len(r.coincidencias) > 0
    assert 0.0 <= r.scoreArea <= 10.0
    assert "mancha" in r.camadasArea
    for c in r.coincidencias:
        assert 0.0 <= c.score <= 10.0
        assert set(c.camadas).issubset(CAMADAS_VALIDAS)
        assert "mancha" in c.camadas
        assert c.nOcorrencias > 0
        assert isinstance(c.provenance, M.Provenance)
        # sempre há a fonte quantitativa da mancha
        assert any(s.kind == "quantitativo" for s in c.provenance.sources)
        # lacuna coerente com camerasRaio
        assert c.cobertura.lacuna == (c.cobertura.camerasRaio == 0)


@pytest.mark.integration
def test_compute_match_camadas_area_validas():
    from app.backend.match.engine import compute_match

    r = compute_match(20)
    assert set(c for c in r.camadasArea).issubset(
        {"mancha", "fator", "dinamica"}
    )
