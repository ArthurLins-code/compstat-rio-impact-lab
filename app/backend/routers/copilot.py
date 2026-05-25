"""Router do copiloto — Trilha 2 (IA & Copiloto).

Endpoints (prefixo /api adicionado no main.py):
  POST /copilot/{area_id}/chat   -> SSE (tool_call/text/suggestion/provenance/done)
  POST /copilot/{area_id}/apply  -> aplica reescrita aceita pelo gestor.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ..ai import copilot

# Trilha 1 (assembler) pode não estar pronta — não bloquear.
try:
    from ..report.assembler import aplicar_edicao  # type: ignore
    _TEM_ASSEMBLER = True
except Exception:  # pragma: no cover
    aplicar_edicao = None  # type: ignore
    _TEM_ASSEMBLER = False

router = APIRouter()

# Fallback em memória quando o assembler ainda não existe (estado por área/seção).
_EDICOES_FALLBACK: Dict[str, Any] = {}


# --------------------------------------------------------------------------- /chat (SSE)
class ChatBody(BaseModel):
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    secaoFoco: Optional[str] = None


@router.post("/copilot/{area_id}/chat")
async def chat(area_id: int, body: ChatBody, request=None):
    """Stream de eventos do copiloto. Cada evento é serializado como JSON em `data:`.

    `usuario` para rate limit/custo (Tarefa 3.5) é o IP da origem — placeholder
    até proximas_ideias.MD#3 trazer login.
    """
    from fastapi import Request as _Req
    # FastAPI injeta automaticamente o Request quando o tipo bate.
    usuario = "anonimo"
    if isinstance(request, _Req):
        usuario = "ip:" + (request.client.host if request.client else "desconhecido")

    def gen():
        for evento in copilot.stream_chat(area_id, body.messages, body.secaoFoco, usuario=usuario):
            yield {"data": json.dumps(evento, ensure_ascii=False, default=str)}

    return EventSourceResponse(gen())


# --------------------------------------------------------------------------- /apply
class ApplyBody(BaseModel):
    secao: str
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.post("/copilot/{area_id}/apply")
def apply(area_id: int, body: ApplyBody):
    """Aplica a reescrita aceita pelo gestor (via assembler, ou fallback em memória)."""
    if _TEM_ASSEMBLER and aplicar_edicao is not None:
        try:
            # `autor='ia'`: sugestão veio do copiloto, mesmo que o gestor tenha
            # clicado "aceitar" — marca para o diff humano×IA (Tarefa 2.4).
            aplicar_edicao(area_id, body.secao, body.payload, autor="ia")
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "erro": str(e)}
    # Fallback: guarda localmente até a Trilha 1 expor o assembler.
    _EDICOES_FALLBACK[f"{area_id}:{body.secao}"] = body.payload
    return {"ok": True, "fallback": True}
