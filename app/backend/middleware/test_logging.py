"""Testes do middleware de logging estruturado."""
from __future__ import annotations

import json
import logging

import pytest


def test_extrai_area_id_de_paths_conhecidos():
    from app.backend.middleware.logging import _area_id_do_path

    assert _area_id_do_path("/api/report/20") == 20
    assert _area_id_do_path("/api/report/20/temporal") == 20
    assert _area_id_do_path("/api/areas/9/acoes") == 9
    assert _area_id_do_path("/api/areas/11/map") == 11


def test_extrai_area_id_ausente_devolve_none():
    from app.backend.middleware.logging import _area_id_do_path

    assert _area_id_do_path("/api/health") is None
    assert _area_id_do_path("/api/areas") is None  # /areas sem /{id}
    assert _area_id_do_path("/api/acoes/123") is None  # acao_id, não area_id


@pytest.mark.integration
def test_middleware_emite_json_e_seta_header_request_id(caplog):
    pytest.importorskip("starlette")
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    from app.backend.middleware.logging import RequestLoggingMiddleware

    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/api/report/20")
    def _h():
        return {"ok": True}

    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger="compstat.req"):
        r = client.get("/api/report/20")
    assert r.status_code == 200
    assert "X-Request-ID" in r.headers

    # Pelo menos uma linha JSON com area_id=20 e status=200.
    linhas = [rec.message for rec in caplog.records if rec.name == "compstat.req"]
    assert linhas, "middleware não emitiu log"
    payload = json.loads(linhas[-1])
    assert payload["area_id"] == 20
    assert payload["status"] == 200
    assert payload["method"] == "GET"
    assert payload["request_id"] == r.headers["X-Request-ID"]
