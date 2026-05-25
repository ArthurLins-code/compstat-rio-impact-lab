"""Copiloto conversacional (Trilha 2): gerador de eventos SSE.

`stream_chat(area_id, messages, secao_foco)` é um GERADOR que produz dicts de evento:
  {"type":"tool_call","tool":..,"friendlyLabel":..}
  {"type":"text","delta":..}
  {"type":"suggestion","sectionId":..,"blockId":..,"currentText":..,"proposedText":..,"provenance":{...}}
  {"type":"provenance","provenance":{...}}
  {"type":"done"}
  {"type":"error","message":..}

Usa client.messages.stream(...) com as ferramentas de consulta (ai.tools) e faz o loop de
tool use (executa via tools.executar_tool e devolve tool_result). Sem chave -> erro + done.
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

from .. import config
from . import prompts_runtime as PR
from . import tools as T

_MAX_TURNOS_TOOL = 6  # teto de iterações do loop de tool use (proteção contra laço)
_AVISO_INDICIO = "Disque/RELINT são indícios, não fatos"

_SECOES_VALIDAS = {"resumo_executivo", "dinamica_criminal", "efetivo_fm", "plano_acao"}


# --------------------------------------------------------------------------- tool de reescrita
def _tool_reescrita() -> Dict[str, Any]:
    """Ferramenta para o modelo PROPOR a reescrita de uma seção (gera evento 'suggestion')."""
    return {
        "name": "propor_reescrita_secao",
        "description": (
            "Use APENAS quando o gestor pedir para reescrever, melhorar ou ajustar uma seção do "
            "relatório. Proponha o novo texto da seção. A reescrita é uma SUGESTÃO que o gestor "
            "decide aceitar — a decisão é dele."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sectionId": {
                    "type": "string",
                    "enum": sorted(_SECOES_VALIDAS),
                    "description": "A seção do relatório a reescrever.",
                },
                "proposedText": {
                    "type": "string",
                    "description": "O novo texto proposto para a seção, em linguagem de gestor.",
                },
                "explicacao_negocio": {
                    "type": "string",
                    "description": "Por que esta redação melhora a seção (1-2 frases).",
                },
                "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
                "fontes_usadas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Rótulos das fontes consultadas que sustentam a reescrita.",
                },
            },
            "required": ["sectionId", "proposedText"],
            "additionalProperties": False,
        },
    }


def _todas_tools() -> List[Dict[str, Any]]:
    return T.definir_tools() + [_tool_reescrita()]


# --------------------------------------------------------------------------- proveniência (chat)
def _kind_fonte(rotulo: str) -> str:
    r = (rotulo or "").lower()
    if "disque" in r:
        return "disque"
    if "relint" in r or "inteligência" in r or "inteligencia" in r:
        return "relint"
    if "fator" in r:
        return "fator"
    if "câmera" in r or "camera" in r or "coincid" in r:
        return "quantitativo"
    return "quantitativo"


def _provenance_de_consultas(consultadas: List[str], fontes_modelo: List[str]) -> Dict[str, Any]:
    """Monta uma proveniência de negócio a partir das ferramentas que o servidor executou."""
    rotulo_por_tool = {
        "consultar_ocorrencias": ("quantitativo", "Registros de ocorrências"),
        "consultar_distribuicao_por_tipo": ("quantitativo", "Distribuição por tipo de crime"),
        "consultar_padrao_temporal": ("quantitativo", "Padrão por dia e horário"),
        "consultar_fatores_urbanos": ("fator", "Fatores urbanos"),
        "consultar_relatos_disque": ("disque", "Relatos do Disque Denúncia"),
        "consultar_dinamica_extraida": ("relint", "Dinâmica criminal (RELINT/Disque)"),
        "consultar_coincidencias": ("quantitativo", "Coincidências espaciais"),
    }
    sources = []
    usou_indicio = False
    for tool in consultadas:
        kind_label = rotulo_por_tool.get(tool)
        if not kind_label:
            continue
        kind, label = kind_label
        if kind in ("disque", "relint"):
            usou_indicio = True
        sources.append({"kind": kind, "label": label})
    # Fontes que o modelo citou e que não vieram de tool (raro): inclui como rótulo.
    for f in fontes_modelo or []:
        if not any(s["label"].lower() == f.lower() for s in sources):
            sources.append({"kind": _kind_fonte(f), "label": f})
    warnings = [_AVISO_INDICIO] if usou_indicio else []
    return {"sources": sources, "warnings": warnings, "usou_indicio": usou_indicio}


# --------------------------------------------------------------------------- gerador principal
def stream_chat(
    area_id: int,
    messages: List[Dict[str, Any]],
    secao_foco: Optional[str] = None,
    usuario: str = "anonimo",
) -> Iterator[Dict[str, Any]]:
    """Gera eventos do chat para SSE. `area_id` é a única área em escopo (server-fixed).

    Quando `config.PERSISTENT_STATE`, cada chamada vira uma linha em
    `copilot_eventos` (registrada no início, consolidada com tokens/custo
    no `done`). `usuario` é placeholder até existir login.

    Guardrails (Tarefa 3.5) rodam antes da auditoria — rate limit, kill
    switch e teto diário de custo. Cada um devolve uma mensagem amigável
    diferente.
    """
    # Guardrails operacionais — falham antes de qualquer call ao Claude.
    from . import guardrails as _G
    try:
        _G.verificar_todos(usuario=usuario)
    except _G.RateLimitError as e:
        yield {"type": "error", "message": "Muitas requisições seguidas. Aguarde um instante."}
        yield {"type": "done"}
        return
    except _G.IADesativada as e:
        yield {"type": "error", "message": str(e)}
        yield {"type": "done"}
        return
    except _G.OrcamentoExcedido as e:
        yield {"type": "error", "message": str(e)}
        yield {"type": "done"}
        return

    # Trilha de auditoria (Tarefa 3.1) — só quando o banco está ligado.
    evento_id = None
    if config.PERSISTENT_STATE:
        try:
            from ..db import auditoria as _AUD
            evento_id = _AUD.registrar(
                area_id=area_id,
                secao_foco=secao_foco,
                usuario=usuario,
                prompt_nome="copiloto",
                prompt_hash_str=_AUD.hash_prompt(PR.SYS_COPILOTO),
            )
        except Exception:  # pragma: no cover - auditoria nunca pode bloquear o chat
            evento_id = None

    if not config.has_api_key():
        yield {
            "type": "error",
            "message": (
                "O copiloto está indisponível: a chave de acesso ao modelo não está configurada "
                "no servidor. Os dados e o mapa da área seguem disponíveis."
            ),
        }
        yield {"type": "done"}
        return

    import anthropic

    client = anthropic.Anthropic(timeout=120.0, max_retries=2)

    system_text = PR.SYS_COPILOTO + f"\n\nÁrea em escopo: Força Municipal {area_id} (período 2023-2024)."
    if secao_foco and secao_foco in _SECOES_VALIDAS:
        system_text += (
            f"\nO gestor está com foco na seção '{secao_foco}'. Se ele pedir para reescrevê-la, "
            "use a ferramenta propor_reescrita_secao."
        )
    system = [{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}]

    # Conversa: sanitiza as mensagens recebidas (apenas role/content de texto do usuário/assistente).
    conv: List[Dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            conv.append({"role": role, "content": content})
    if not conv:
        yield {"type": "error", "message": "Nenhuma mensagem do usuário foi recebida."}
        yield {"type": "done"}
        return

    tools = _todas_tools()
    consultadas: List[str] = []  # ferramentas de consulta executadas nesta interação

    # Acumuladores para consolidar a auditoria no final.
    tokens_in_total = 0
    tokens_out_total = 0
    resposta_texto: List[str] = []

    try:
        for _turno in range(_MAX_TURNOS_TOOL):
            tool_uses: List[Any] = []
            with client.messages.stream(
                model=config.MODEL,
                max_tokens=2048,
                system=system,
                tools=tools,
                messages=conv,
            ) as stream:
                for event in stream:
                    if event.type == "content_block_delta" and getattr(event.delta, "type", None) == "text_delta":
                        delta = event.delta.text
                        if delta:
                            resposta_texto.append(delta)
                            yield {"type": "text", "delta": delta}
                final = stream.get_final_message()
                # Anthropic devolve usage no final.message.usage
                usage = getattr(final, "usage", None)
                if usage is not None:
                    tokens_in_total += int(getattr(usage, "input_tokens", 0) or 0)
                    tokens_out_total += int(getattr(usage, "output_tokens", 0) or 0)

            # Sem tool use -> resposta final; emite proveniência (se houve consultas) e encerra.
            if final.stop_reason != "tool_use":
                if consultadas:
                    prov = _provenance_de_consultas(consultadas, [])
                    yield {
                        "type": "provenance",
                        "provenance": {
                            "rationale": "Resposta fundamentada nos dados consultados da área.",
                            "confidence": "media",
                            "sources": prov["sources"],
                            "warnings": prov["warnings"],
                        },
                    }
                if evento_id is not None:
                    try:
                        from ..db import auditoria as _AUD
                        _AUD.consolidar(
                            evento_id,
                            tokens_in=tokens_in_total,
                            tokens_out=tokens_out_total,
                            ferramentas=list(set(consultadas)),
                            resposta_resumo="".join(resposta_texto)[:500],
                            modelo=config.MODEL,
                        )
                    except Exception:  # pragma: no cover
                        pass
                yield {"type": "done"}
                return

            # Há tool use: registra o turno do assistente e processa cada chamada.
            tool_uses = [b for b in final.content if getattr(b, "type", None) == "tool_use"]
            conv.append({"role": "assistant", "content": final.content})
            tool_results: List[Dict[str, Any]] = []

            for tu in tool_uses:
                nome = tu.name

                # --- reescrita de seção: emite 'suggestion' e devolve confirmação ao modelo ---
                if nome == "propor_reescrita_secao":
                    args = tu.input or {}
                    section_id = args.get("sectionId") or secao_foco or "resumo_executivo"
                    proposed = args.get("proposedText", "")
                    prov_meta = _provenance_de_consultas(consultadas, args.get("fontes_usadas") or [])
                    warnings = list(prov_meta["warnings"])
                    suggestion_prov = {
                        "rationale": args.get("explicacao_negocio")
                        or "Reescrita sugerida a partir dos dados da área.",
                        "confidence": args.get("confianca") or "media",
                        "sources": prov_meta["sources"],
                        "warnings": warnings,
                    }
                    yield {
                        "type": "suggestion",
                        "sectionId": section_id,
                        "blockId": f"{section_id}:{area_id}",
                        "currentText": None,  # o frontend conhece o texto atual da seção
                        "proposedText": proposed,
                        "provenance": suggestion_prov,
                    }
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": (
                                "Sugestão de reescrita apresentada ao gestor para decisão. "
                                "Confirme ao usuário que ele pode aceitar ou ajustar."
                            ),
                        }
                    )
                    continue

                # --- consulta de dados ---
                result = T.executar_tool(nome, area_id, tu.input or {})
                if nome in T._CATALOGO:
                    consultadas.append(nome)
                label = T.friendly_label(nome, tu.input or {}, result)
                yield {"type": "tool_call", "tool": nome, "friendlyLabel": label}

                # Entrega ao modelo um resultado de NEGÓCIO (texto), nunca JSON cru à UI.
                payload = result.get("resultado") if result.get("ok") else None
                conteudo_modelo = _resultado_para_modelo(nome, label, payload, result)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": tu.id, "content": conteudo_modelo}
                )

            conv.append({"role": "user", "content": tool_results})

        # Excedeu o teto de turnos de tool use.
        yield {
            "type": "text",
            "delta": "\n\n(Consulta interrompida por limite de etapas. Reformule a pergunta, por favor.)",
        }
        yield {"type": "done"}
    except Exception as e:  # falha de rede/API: degrada com mensagem amigável
        yield {
            "type": "error",
            "message": "Houve uma falha ao conversar com o modelo. Tente novamente em instantes.",
        }
        # detalhe técnico não vai para a UI; mantém só a mensagem amigável.
        _ = str(e)
        yield {"type": "done"}


def _resultado_para_modelo(nome: str, label: str, payload: Any, result: Dict[str, Any]) -> str:
    """Texto entregue ao MODELO como tool_result (estruturado, mas legível; sem SQL).

    O modelo precisa dos números/itens para raciocinar; serializamos de forma compacta e segura.
    """
    import json as _json

    if not result.get("ok"):
        return f"{label} Não há dados disponíveis: {result.get('erro', 'sem detalhes')}."
    if payload is None:
        obs = result.get("observacao")
        return f"{label}" + (f" {obs}" if obs else " (sem dados para esta área).")
    try:
        corpo = _json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        corpo = str(payload)
    # Trunca payloads muito grandes para não estourar tokens.
    if len(corpo) > 6000:
        corpo = corpo[:6000] + " …(resultado truncado)"
    return f"{label}\nDados: {corpo}"
