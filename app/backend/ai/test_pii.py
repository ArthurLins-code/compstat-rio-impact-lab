"""Testes de redação de PII — defesa em profundidade do contrato público."""
from __future__ import annotations

from app.backend.ai import pii as P


# ---------------------------------------------------------------------------
# Padrões básicos (CPF, telefone, e-mail, RG)
# ---------------------------------------------------------------------------


def test_redact_cpf_formatado():
    assert "[CPF]" in P.redact("informou CPF 123.456.789-00 ao agente")
    # E o número não pode aparecer no resultado.
    assert "123.456.789" not in P.redact("CPF 123.456.789-00")


def test_redact_cpf_sem_formato():
    assert "[CPF]" in P.redact("CPF 12345678900 confirmado")


def test_redact_telefone_com_ddd():
    out = P.redact("ligar para (21) 99876-1234 e confirmar")
    assert "[TELEFONE]" in out
    assert "99876-1234" not in out


def test_redact_email():
    out = P.redact("denúncia enviada por suspeito@example.com.br")
    assert "[EMAIL]" in out
    assert "suspeito@example" not in out


def test_redact_rg_formatado():
    assert "[RG]" in P.redact("RG 12.345.678-9 do indivíduo")


def test_redact_nao_quebra_quando_texto_eh_none():
    assert P.redact(None) == ""
    assert P.redact("") == ""


# ---------------------------------------------------------------------------
# Heurística de nome
# ---------------------------------------------------------------------------


def test_nome_proprio_simples_eh_mascarado():
    out = P.redact("Joao Silva foi visto na esquina")
    assert "[NOME]" in out
    assert "Joao Silva" not in out


def test_nome_com_conectivo_eh_mascarado():
    out = P.redact("foi citado Maria de Souza no relato")
    assert "[NOME]" in out


def test_toponimo_nao_eh_confundido_com_nome():
    # "Rua das Laranjeiras" tem palavras capitalizadas mas é topônimo.
    out = P.redact("ocorrência na Rua das Laranjeiras")
    assert "[NOME]" not in out


def test_palavra_unica_capitalizada_nao_dispara():
    # "Botafogo" sozinho não é nome próprio de pessoa.
    out = P.redact("área de Botafogo apresenta")
    assert out == "área de Botafogo apresenta"


# ---------------------------------------------------------------------------
# Recursão em estruturas
# ---------------------------------------------------------------------------


def test_redact_dict_aninhado():
    entrada = {
        "tema": "denuncia",
        "metadados": {
            "telefone": "21 99876 1234",
            "email": "x@y.com",
            "tags": ["CPF 123.456.789-00", "ok"],
        },
    }
    saida = P.redact_dict(entrada)
    assert "[TELEFONE]" in saida["metadados"]["telefone"]
    assert "[EMAIL]" in saida["metadados"]["email"]
    assert "[CPF]" in saida["metadados"]["tags"][0]
    assert saida["metadados"]["tags"][1] == "ok"


def test_filtrar_campos_proibidos():
    entrada = {"category": "x", "relato_redacted": "txt", "envolvidos": {"nome": "y"}, "qtd": 5}
    saida = P.filtrar_campos_proibidos(entrada)
    assert "relato_redacted" not in saida
    assert "envolvidos" not in saida
    assert saida == {"category": "x", "qtd": 5}
