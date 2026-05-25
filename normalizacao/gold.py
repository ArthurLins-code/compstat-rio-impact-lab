"""Camada gold — agregados por área FM, prontos para o match consumir.

Gera `area_brief.csv` (1 linha por área, wide) + tabelas longas de drill-down.
A seção de dinâmica é preenchida a partir de `dinamica_extraida.csv` (saída do LLM)
quando este existir; caso contrário fica marcada como pendente.
"""
import json

import pandas as pd

from . import config as C


def _j(obj):
    return json.dumps(obj, ensure_ascii=False)


def _read_silver(name):
    return pd.read_csv(C.OUT_SILVER / name)


def build_gold():
    areas = _read_silver("dim_area_fm.csv")
    occ = _read_silver("fact_ocorrencias.csv")
    fat = _read_silver("fact_fatores_urbanos.csv")
    cam = _read_silver("fact_cameras.csv")
    dd = _read_silver("fact_disque_denuncia.csv")
    cpsr = _read_silver("agg_cpsr_area_ano.csv")
    dom = pd.read_csv(C.OUT_SILVER / "dim_dominio_territorial.csv", dtype={"area_fm_ids": str})

    occ_a = occ[occ["area_fm_id"].notna()].copy()
    fat_a = fat[fat["area_fm_id"].notna()].copy()
    occ_a["area_fm_id"] = occ_a["area_fm_id"].astype(int)
    fat_a["area_fm_id"] = fat_a["area_fm_id"].astype(int)

    # ---- tabelas longas (drill-down) ----
    g_tipo = (occ_a.groupby(["area_fm_id", "category"]).size()
              .reset_index(name="qtd").sort_values(["area_fm_id", "qtd"], ascending=[True, False]))
    g_tipo.to_csv(C.OUT_GOLD / "gold_ocorrencias_tipo.csv", index=False)

    g_temp = (occ_a.dropna(subset=["dia_semana", "hora"])
              .groupby(["area_fm_id", "dia_semana", "hora"]).size().reset_index(name="qtd"))
    g_temp["hora"] = g_temp["hora"].astype(int)
    g_temp.to_csv(C.OUT_GOLD / "gold_temporal.csv", index=False)

    g_forg = (fat_a.groupby(["area_fm_id", "category", "orgao_responsavel"]).size()
              .reset_index(name="qtd").sort_values(["area_fm_id", "qtd"], ascending=[True, False]))
    g_forg.to_csv(C.OUT_GOLD / "gold_fatores_orgao.csv", index=False)

    # ---- dinâmica (LLM), se já extraída ----
    din_path = C.OUT_SILVER / "dinamica_extraida.csv"
    din = pd.read_csv(din_path) if din_path.exists() else None

    # ranking por total de ocorrências
    tot = occ_a.groupby("area_fm_id").size()
    rank = tot.rank(ascending=False, method="min").astype(int)

    rows = []
    for _, a in areas.iterrows():
        aid = int(a["area_fm_id"])
        o = occ_a[occ_a["area_fm_id"] == aid]
        f = fat_a[fat_a["area_fm_id"] == aid]
        total = int(len(o))

        # distribuição por tipo
        tipos = o["category"].value_counts()
        por_tipo = {k: int(v) for k, v in tipos.items()}

        # matriz temporal -> top células de pico
        tt = g_temp[g_temp["area_fm_id"] == aid].sort_values("qtd", ascending=False)
        janelas = [{"dia": r.dia_semana, "hora": int(r.hora), "qtd": int(r.qtd)}
                   for r in tt.head(3).itertuples()]
        pico_dia = janelas[0]["dia"] if janelas else None
        pico_hora = janelas[0]["hora"] if janelas else None

        # fatores por tipo e por órgão
        fat_tipo = {k: int(v) for k, v in f["category"].value_counts().items()}
        fat_org = {k: int(v) for k, v in f["orgao_responsavel"].dropna().value_counts().items()}

        # cpsr agregado e facções
        n_psr = int(cpsr.loc[cpsr["area_fm_id"] == aid, "n_pessoas"].sum())
        fac = dom[dom["area_fm_ids"].fillna("").apply(
            lambda s: aid in [int(float(x)) for x in str(s).split(";") if x not in ("", "nan")])]
        faccoes = sorted(fac["dominio_orcrim"].dropna().unique().tolist())

        n_cam = int((cam["area_fm_id"] == aid).sum())
        n_dd = int((dd["area_fm_id"] == aid).sum())

        # dinâmica (LLM) — consolida afirmações da área se disponível
        if din is not None:
            d = din[din["area_fm_id"] == aid]
            dinamica = {
                "modalidade": sorted(d.loc[d["campo"] == "modalidade_criminal", "valor"].dropna().unique().tolist()),
                "modus_operandi": d.loc[d["campo"] == "modus_operandi", "valor"].dropna().tolist(),
                "rotas_fuga": d.loc[d["campo"] == "rotas_fuga", "valor"].dropna().tolist(),
                "deslocamento": sorted(d.loc[d["campo"] == "deslocamento_autor", "valor"].dropna().unique().tolist()),
            }
            fontes = sorted(d["doc_id"].dropna().unique().tolist())
            confianca = "ver dinamica_extraida.csv"
        else:
            dinamica = {"_status": "pendente_extracao_llm"}
            fontes = []
            confianca = "pendente"

        avisos = [
            "Rascunho automático — priorização e decisão final são humanas.",
            "Ocorrências cobrem apenas roubo (sem furto).",
            "Disque Denúncia e domínio territorial são indícios; citar a fonte.",
        ]

        rows.append({
            "area_fm_id": aid,
            "nome_area": a["nome_subarea"],
            "total_ocorrencias": total,
            "ranking_ocorrencias": int(rank.get(aid, 0)),
            "n_disque": n_dd,
            "n_cameras": n_cam,
            "n_psr_cpsr": n_psr,
            "pico_dia_semana": pico_dia,
            "pico_hora": pico_hora,
            "ocorrencias_por_tipo": _j(por_tipo),
            "janelas_pico": _j(janelas),
            "fatores_por_tipo": _j(fat_tipo),
            "fatores_por_orgao": _j(fat_org),
            "faccoes_influencia": _j(faccoes),
            "dinamica": _j(dinamica),
            "fontes_dinamica": _j(fontes),
            "confianca_dinamica": confianca,
            "avisos": _j(avisos),
            "geometry_wkt": a["geometry_wkt"],
        })

    brief = pd.DataFrame(rows).sort_values("ranking_ocorrencias")
    brief.to_csv(C.OUT_GOLD / "area_brief.csv", index=False)
    return brief, (din is not None)
