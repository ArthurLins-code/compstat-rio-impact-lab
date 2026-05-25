"""Constantes e caminhos da camada de normalização CompStat Rio."""
import os
from pathlib import Path

# Raiz do repositório: um nível acima deste arquivo (normalizacao/config.py).
# Override possível via COMPSTAT_DATA_ROOT (ex.: container montando volume).
BASE = Path(
    os.environ.get("COMPSTAT_DATA_ROOT")
    or Path(__file__).resolve().parents[1]
)
DADOS = BASE / "dados"
OUT = BASE / "dados_normalizados"
OUT_SILVER = OUT / "silver"
OUT_GOLD = OUT / "gold"

# Arquivos de entrada (caminhos reais verificados)
F_OCORRENCIAS = DADOS / "df_ocorrencias_tratado - Extração 1 .csv"
F_DISQUE = DADOS / "disk_denuncia.csv"
F_FATORES = DADOS / "fatores_urbanos.csv"
F_CAMERAS = DADOS / "cameras_areas_fm.csv"
F_DOMINIO = DADOS / "outros dados" / "dominio_territorial - Extração 1.csv"
F_CPSR = DADOS / "outros dados" / "CPSR_2020_2022_2024.xlsx"
F_SHP = BASE / "sh_area_forca" / "areas_forca_municipal.shp"
D_RELINTS = BASE / "relints"

# Bounding box do município do Rio de Janeiro (lon/lat WGS84)
LON_MIN, LON_MAX = -43.80, -43.10
LAT_MIN, LAT_MAX = -23.10, -22.74

# fids dos 8 polígonos da Força Municipal (subconjunto não contíguo)
AREA_FM_IDS = [2, 9, 10, 11, 12, 14, 19, 20]

# Esquema canônico do fato espacial (ordem das colunas no CSV)
FACT_COLUMNS = [
    "fact_id", "source", "layer", "lat", "lon", "geom_quality",
    "area_fm_id", "area_fm_nome", "bairro", "ano", "mes", "hora", "dia_semana",
    "category", "orgao_responsavel", "attributes_json",
    "prov_file", "prov_row_id", "ingested_at",
]

# Normalização de dia da semana (alguns vêm sem acento)
DIA_SEMANA_CANON = {
    "segunda": "Segunda", "terca": "Terça", "terça": "Terça",
    "quarta": "Quarta", "quinta": "Quinta", "sexta": "Sexta",
    "sabado": "Sábado", "sábado": "Sábado", "domingo": "Domingo",
}
# Mapa: índice weekday() do Python -> nome canônico (para derivar de datas)
WEEKDAY_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
