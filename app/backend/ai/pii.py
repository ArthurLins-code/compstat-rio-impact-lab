"""Redação de PII (LGPD) — Tarefa 3.4.

Aplica regex BR conservadoras + heurística leve de nome para mascarar
dados pessoais antes do conteúdo sair do servidor. Mantém o tipo de
informação visível (`[NOME]`, `[TELEFONE]`) para preservar legibilidade
do gestor sem expor o dado.

Princípio: prefira mascarar de mais do que de menos. Falso-positivo
ofusca a leitura; falso-negativo viola LGPD.

Não substitui Presidio (que tem ML + dicionário de nomes); é um filtro
defensivo, complementar à redação já feita na pipeline `normalizacao/`.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

# CPF: 11 dígitos, opcionalmente formatado.
_RE_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")

# RG: 7-9 dígitos + dígito verificador (X|0-9), variantes UF (RJ comum).
_RE_RG = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]\b")

# Telefone BR: (XX) 9XXXX-XXXX, opcional DDI +55, opcional 8/9 dígitos no número.
_RE_TEL = re.compile(
    r"(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\s*\d{4}[-\.\s]?\d{4}\b"
)

# E-mail: padrão RFC simplificado (suficiente para mascarar).
_RE_EMAIL = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w{2,}\b")

# Nome próprio: 2+ palavras capitalizadas em sequência (heurística).
# Stop-words evitam falsos positivos triviais ("Rua das Laranjeiras", etc.).
_STOP_NOMES = {
    "Rua", "Avenida", "Av", "Travessa", "Estrada", "Largo", "Praça", "Praca",
    "Rio", "Janeiro", "Sao", "São", "Santo", "Santa", "Forca", "Força",
    "Centro", "Botafogo", "Tijuca", "Copacabana", "Ipanema", "Leblon",
    "Disque", "Denúncia", "Denuncia", "Polícia", "Policia", "Brasil",
    "Norte", "Sul", "Leste", "Oeste", "Estado", "Município", "Municipio",
    "RJ", "SP", "MG",
}
# Nome próprio: token capitalizado seguido por ≥1 (conectivo OU outro token capitalizado),
# capturando até 4 partes. Conectivo nunca pode ser o último — Maria de = topônimo improvável.
_RE_NOME = re.compile(
    r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+"
    r"(?:\s+(?:da|de|do|das|dos|e))*"
    r"(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+){1,3})\b"
)


_CONECTIVOS = {"da", "de", "do", "das", "dos", "e"}


def _eh_nome(candidato: str) -> bool:
    """Filtra falsos positivos do regex de nome."""
    palavras = re.split(r"\s+", candidato.strip())
    relevantes = [p for p in palavras if p.lower() not in _CONECTIVOS]
    if len(relevantes) < 2:
        return False  # nome próprio de pessoa típico tem ≥2 tokens reais
    # Se alguma palavra relevante é stop-word óbvia, presume topônimo.
    if any(p in _STOP_NOMES for p in relevantes):
        return False
    return True


def redact(texto: str) -> str:
    """Mascara PII no texto. Devolve uma string segura para o cliente.

    Ordem importa: CPF/RG/Telefone/E-mail antes de Nome (Nome é heurístico
    e poderia varrer dígitos formatados de outras categorias).
    """
    if not texto:
        return texto or ""
    texto = _RE_EMAIL.sub("[EMAIL]", texto)
    texto = _RE_CPF.sub("[CPF]", texto)
    texto = _RE_RG.sub("[RG]", texto)
    texto = _RE_TEL.sub("[TELEFONE]", texto)

    def _nome_sub(m: "re.Match") -> str:
        return "[NOME]" if _eh_nome(m.group(1)) else m.group(0)

    texto = _RE_NOME.sub(_nome_sub, texto)
    return texto


def redact_dict(payload: Any) -> Any:
    """Aplica `redact` recursivamente em todas as strings de um dict/list."""
    if isinstance(payload, str):
        return redact(payload)
    if isinstance(payload, dict):
        return {k: redact_dict(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [redact_dict(v) for v in payload]
    return payload


# Campos que jamais devem sair do servidor mesmo já tendo passado por `redact`.
CAMPOS_PROIBIDOS = {
    "relato_redacted",  # texto cru do Disque
    "relato",
    "denuncia_texto",
    "envolvidos",       # bloco com nome/idade/cor
    "attributes_json",  # JSON cru pode trazer logradouro/coords precisas
}


def filtrar_campos_proibidos(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Remove campos que não podem nunca sair do servidor (contrato público)."""
    if not isinstance(payload, dict):
        return payload
    return {k: v for k, v in payload.items() if k not in CAMPOS_PROIBIDOS}
