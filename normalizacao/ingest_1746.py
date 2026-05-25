"""Ingestão de chamados do 1746 como fator urbano adicional.

Tem dois modos:

1. `from_bigquery(...)`: puxa do dataset público `datario.adm_central_atendimento_1746.chamado`
   no BigQuery. Requer `google-cloud-bigquery` e credencial GCP
   (`GOOGLE_APPLICATION_CREDENTIALS` ou `COMPSTAT_GCP_PROJECT`). **Esta máquina
   não tem credencial** — esse modo fica pronto para a Prefeitura ligar
   billing na Fase 5.

2. `from_snapshot(path)`: lê um CSV-snapshot local. Caminho default
   `dados_normalizados/silver/fact_chamados_1746.csv` — usado como fallback
   determinístico em dev/CI.

Sempre devolve um DataFrame no esquema canônico `FACT_COLUMNS` (ver
`config.py`), pronto para virar mais um `fact_*` na silver.

Uso CLI:

    python -m normalizacao.ingest_1746 --snapshot caminho.csv \
        --out dados_normalizados/silver/fact_chamados_1746.csv

Sem `--snapshot`, tenta BigQuery e falha com mensagem clara se não houver
credencial. Sem `--out`, imprime preview (10 linhas) e não grava.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from . import config as C
from .mapa_1746_para_fator import CATEGORIA_FONTE, mapear

# Esquema mínimo esperado no snapshot/BigQuery (renames opcionais via params).
COLUNAS_FONTE_DEFAULT = {
    "id": "id_chamado",
    "tipo": "tipo",
    "subtipo": "subtipo",
    "status": "status",
    "data": "data_inicio",
    "lat": "latitude",
    "lon": "longitude",
    "bairro": "nome_bairro",
}

# Status considerados "resolvidos" — só esses entram na silver para evitar
# inflar o agregado com chamado novo/duplicado.
STATUS_FECHADOS = {"fechado", "atendido", "encerrado", "concluido"}


# ---------------------------------------------------------------------------
# Modo 1: BigQuery (não usado nesta fase — sem credencial na máquina)
# ---------------------------------------------------------------------------

_BQ_QUERY = """
SELECT
  id_chamado, tipo, subtipo, status,
  data_inicio, latitude, longitude, nome_bairro
FROM `datario.adm_central_atendimento_1746.chamado`
WHERE data_inicio >= @desde
  AND latitude IS NOT NULL AND longitude IS NOT NULL
  AND LOWER(status) IN UNNEST(@status_ok)
LIMIT @limite
"""


def from_bigquery(
    project: Optional[str] = None,
    desde: str = "2024-01-01",
    limite: int = 200_000,
) -> pd.DataFrame:
    """Pull bruto do 1746 no BigQuery público.

    Não roda nesta máquina: sem `google-cloud-bigquery` instalado e sem
    credencial. Levanta `RuntimeError` com instrução clara.
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "google-cloud-bigquery não instalado. Use `from_snapshot(path)` ou "
            "`pip install google-cloud-bigquery` + credencial GCP."
        ) from e

    proj = project or os.environ.get("COMPSTAT_GCP_PROJECT")
    if not proj and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        raise RuntimeError(
            "Sem credencial GCP. Defina COMPSTAT_GCP_PROJECT ou "
            "GOOGLE_APPLICATION_CREDENTIALS antes de chamar from_bigquery."
        )

    client = bigquery.Client(project=proj)
    job = client.query(
        _BQ_QUERY,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("desde", "DATE", desde),
                bigquery.ArrayQueryParameter("status_ok", "STRING", sorted(STATUS_FECHADOS)),
                bigquery.ScalarQueryParameter("limite", "INT64", limite),
            ]
        ),
    )
    return job.result().to_dataframe(create_bqstorage_client=False)


# ---------------------------------------------------------------------------
# Modo 2: snapshot local (caminho usado em dev/CI hoje)
# ---------------------------------------------------------------------------


def from_snapshot(path: Optional[str] = None) -> pd.DataFrame:
    """Lê o snapshot CSV do 1746. Default: silver/fact_chamados_1746.csv."""
    p = path or str(C.OUT_SILVER / "fact_chamados_1746.csv")
    if not os.path.exists(p):
        raise FileNotFoundError("Snapshot do 1746 não encontrado em %s" % p)
    return pd.read_csv(p)


# ---------------------------------------------------------------------------
# Normalização para o esquema canônico FACT_COLUMNS
# ---------------------------------------------------------------------------


def _categoria_e_orgao(row: pd.Series) -> Optional[pd.Series]:
    pair = mapear(row.get("tipo"), row.get("subtipo"))
    if pair is None:
        return None
    return pd.Series({"category": pair[0], "orgao_responsavel": pair[1]})


def normalize(bruto: pd.DataFrame) -> pd.DataFrame:
    """Aplica mapa de categorias + esquema FACT_COLUMNS.

    Não faz spatial-join para atribuir `area_fm_id`: isso depende da pipeline
    `normalizacao/silver.py` (usa shapely sobre dim_area_fm). Se o bruto já
    tiver `area_fm_id` preenchido (snapshot), ele é preservado; caso
    contrário fica em branco e a próxima rodada do silver completa.
    """
    if bruto.empty:
        return pd.DataFrame(columns=C.FACT_COLUMNS)

    # Filtra só status fechados (evita inflar com chamado em aberto).
    if "status" in bruto.columns:
        bruto = bruto[bruto["status"].astype(str).str.lower().isin(STATUS_FECHADOS)]

    # Aplica o catálogo: tipos não mapeados são descartados.
    cat = bruto.apply(_categoria_e_orgao, axis=1)
    bruto = bruto.loc[cat.notna().any(axis=1)].copy()
    bruto[["category", "orgao_responsavel"]] = cat.dropna(how="all")

    # Tempo canônico: derivado de data_inicio quando possível.
    if "data_inicio" in bruto.columns:
        dt = pd.to_datetime(bruto["data_inicio"], errors="coerce", utc=True)
        bruto["ano"] = dt.dt.year
        bruto["mes"] = dt.dt.month
    else:
        bruto["ano"] = pd.NA
        bruto["mes"] = pd.NA

    ingested_at = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")

    out = pd.DataFrame(
        {
            "fact_id": ["chamados_1746:%s" % i for i in bruto.get("id_chamado", range(len(bruto)))],
            "source": "chamados_1746",
            "layer": "fator_urbano",
            "lat": bruto.get("latitude"),
            "lon": bruto.get("longitude"),
            "geom_quality": "ok",
            "area_fm_id": bruto.get("area_fm_id"),
            "area_fm_nome": bruto.get("area_fm_nome"),
            "bairro": bruto.get("nome_bairro"),
            "ano": bruto["ano"],
            "mes": bruto["mes"],
            "hora": pd.NA,
            "dia_semana": pd.NA,
            "category": bruto["category"],
            "orgao_responsavel": bruto["orgao_responsavel"],
            "attributes_json": bruto.apply(
                lambda r: '{"fonte":"%s","tipo":"%s","subtipo":"%s"}'
                % (CATEGORIA_FONTE, r.get("tipo", ""), r.get("subtipo", "")),
                axis=1,
            ),
            "prov_file": "chamado_1746",
            "prov_row_id": range(len(bruto)),
            "ingested_at": ingested_at,
        }
    )
    return out[C.FACT_COLUMNS]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--snapshot", help="Caminho do CSV-snapshot (modo offline).")
    p.add_argument("--out", help="Caminho do CSV de saída (silver).")
    p.add_argument("--desde", default="2024-01-01", help="Data mínima (BigQuery).")
    p.add_argument("--limite", type=int, default=200_000)
    args = p.parse_args(argv)

    bruto = from_snapshot(args.snapshot) if args.snapshot else from_bigquery(
        desde=args.desde, limite=args.limite
    )
    norm = normalize(bruto)

    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        norm.to_csv(args.out, index=False)
        print("Gravado %d linhas em %s" % (len(norm), args.out))
    else:
        print(norm.head(10).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(_main())
