"""Configuração do backend.

Insere a raiz do repositório no sys.path para reusar o pacote `normalizacao`,
carrega o .env e expõe as constantes do backend.
"""
from __future__ import annotations

import os
import pathlib
import sys

# A raiz do repo é 2 níveis acima deste arquivo (app/backend/config.py -> repo/).
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from normalizacao import config as C  # noqa: E402  (reusa caminhos/constantes da pipeline)

# --- Constantes do backend ---
MODEL = os.environ.get("COMPSTAT_MODEL", "claude-sonnet-4-6")
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")]
DISQUE_AMOSTRA_LIMITE = 25

# --- Persistência (Fase 2) ---
# Default off: protege quem já roda em memória. Ligar exige rede interna
# controlada — não há login ainda (proximas_ideias.MD#3).
PERSISTENT_STATE = os.environ.get("COMPSTAT_PERSISTENT_STATE", "0").lower() in {
    "1", "true", "yes", "on",
}
DB_URL = os.environ.get("COMPSTAT_DB_URL", "sqlite:///./compstat.db")

# --- Caminhos e domínio (reusados da pipeline) ---
OUT_GOLD = C.OUT_GOLD
OUT_SILVER = C.OUT_SILVER
AREA_FM_IDS = C.AREA_FM_IDS
WEEKDAY_PT = C.WEEKDAY_PT


def has_api_key() -> bool:
    """Avaliado em runtime (a chave pode ser colada no .env após o servidor subir)."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
