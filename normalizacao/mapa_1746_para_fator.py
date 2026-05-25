"""Mapa tipo/subtipo do 1746 -> (category, orgao_responsavel) do esquema gold.

Catálogo inicial conservador (iluminação, poda, lixo, calçada) — só os tipos
mapeados sobem para `fact_chamados_1746.csv`. Tipos não mapeados são
descartados na normalização, evitando explosão do agregado de fatores.

`CATEGORIA_FONTE` é a sentinela usada no campo `attributes_json` para
marcar a proveniência ("1746"); o backend pode filtrar/ponderar diferente
quando o fator vem de chamado público vs do levantamento original.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

# (tipo_normalizado, subtipo_normalizado) -> (category, orgao_responsavel).
# Normalização: lower + strip + remoção de acentos é aplicada no lookup.
MAPA: Dict[Tuple[str, str], Tuple[str, str]] = {
    # Iluminação pública -> Rio Luz
    ("iluminacao publica", "lampada apagada"): (
        "Área mal iluminada com circulação de pedestres",
        "Rio Luz",
    ),
    ("iluminacao publica", "poste apagado"): (
        "Área mal iluminada com circulação de pedestres",
        "Rio Luz",
    ),
    ("iluminacao publica", ""): (
        "Área mal iluminada com circulação de pedestres",
        "Rio Luz",
    ),
    # Poda / vegetação -> COMLURB
    ("poda de arvore", ""): (
        "Vegetação encobrindo iluminação pública",
        "COMLURB",
    ),
    ("arvore em area publica", "solicitacao de poda"): (
        "Vegetação encobrindo iluminação pública",
        "COMLURB",
    ),
    # Lixo / limpeza -> COMLURB
    ("coleta domiciliar", "lixo acumulado em via publica"): (
        "Acúmulo de lixo em via pública",
        "COMLURB",
    ),
    ("limpeza urbana", "lixo acumulado"): (
        "Acúmulo de lixo em via pública",
        "COMLURB",
    ),
    # Calçada -> SECONSERVA
    ("manutencao de calcada", ""): (
        "Calçada quebrada / obstáculo no passeio",
        "SECONSERVA",
    ),
    ("reparo de buraco em calcada", ""): (
        "Calçada quebrada / obstáculo no passeio",
        "SECONSERVA",
    ),
}

CATEGORIA_FONTE = "1746"


def _norm(s: Optional[str]) -> str:
    """Lower + strip + remove acentos comuns. None vira ''."""
    if not s:
        return ""
    s = s.strip().lower()
    troca = str.maketrans("áàâãäéèêëíïóôõöúüç", "aaaaaeeeeiioooouuc")
    return s.translate(troca)


def mapear(tipo: Optional[str], subtipo: Optional[str]) -> Optional[Tuple[str, str]]:
    """Devolve (category, orgao) ou None se a combinação não estiver no catálogo.

    Tenta o par (tipo, subtipo) e cai para (tipo, '') quando o subtipo não
    casa exatamente — assim chamado novo do mesmo tipo já entra no agregado
    sem novo deploy.
    """
    t, s = _norm(tipo), _norm(subtipo)
    if (t, s) in MAPA:
        return MAPA[(t, s)]
    if (t, "") in MAPA:
        return MAPA[(t, "")]
    return None
