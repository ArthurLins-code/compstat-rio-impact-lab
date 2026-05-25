"""Middleware de logging estruturado por requisição.

Emite uma linha JSON por requisição em `logging.getLogger("compstat.req")`,
contendo `request_id` (uuid4), método, path, duração, status e (quando
houver) `area_id` extraído do path. O `request_id` também volta no header
`X-Request-ID` para correlação cliente↔server.

Não bloqueia em falha de logging — se algo der errado no logger, o
middleware ainda retorna a resposta normalmente.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone

_LOG = logging.getLogger("compstat.req")

# Captura `area_id` em paths como `/api/report/20/...`, `/api/areas/20/acoes`.
_RE_AREA = re.compile(r"/(?:areas|report)/(\d+)(?:/|$)")


def _area_id_do_path(path: str):
    m = _RE_AREA.search(path)
    return int(m.group(1)) if m else None


# Starlette só carrega quando o middleware é efetivamente instanciado pelo
# FastAPI — testes puros (que só usam `_area_id_do_path`) não precisam dele.
try:
    from starlette.middleware.base import BaseHTTPMiddleware as _BaseHTTPMiddleware
    _STARLETTE_OK = True
except ImportError:  # pragma: no cover
    _BaseHTTPMiddleware = object  # type: ignore[misc, assignment]
    _STARLETTE_OK = False


class RequestLoggingMiddleware(_BaseHTTPMiddleware):  # type: ignore[misc, valid-type]
    """Loga cada requisição em JSON com request_id, duração e status."""

    async def dispatch(self, request, call_next):
        if not _STARLETTE_OK:  # pragma: no cover
            raise RuntimeError("starlette ausente — instale FastAPI/starlette antes de subir o app.")
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        start = time.perf_counter()
        status_code = 500  # default se o handler estourar
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            try:
                duration_ms = int((time.perf_counter() - start) * 1000)
                _LOG.info(
                    json.dumps(
                        {
                            "ts": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
                            "level": "INFO",
                            "logger": "compstat.req",
                            "request_id": request_id,
                            "method": request.method,
                            "path": request.url.path,
                            "area_id": _area_id_do_path(request.url.path),
                            "status": status_code,
                            "duration_ms": duration_ms,
                        },
                        ensure_ascii=False,
                    )
                )
            except Exception:  # pragma: no cover - logging nunca pode quebrar resposta
                pass
