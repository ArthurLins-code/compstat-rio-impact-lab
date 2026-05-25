"""Onda 1 — executa o silver determinístico, grava os CSVs e valida (sanity checks)."""
import pandas as pd

from . import config as C
from . import geo, silver


def _pct_ok_bbox(df, label):
    vc = df["geom_quality"].value_counts(dropna=False).to_dict()
    cobertura = df["area_fm_id"].notna().mean() * 100
    print(f"  {label:18s} geom_quality={vc}  | em alguma área FM: {cobertura:.1f}%")
    return vc


def main():
    C.OUT_SILVER.mkdir(parents=True, exist_ok=True)
    C.OUT.mkdir(parents=True, exist_ok=True)
    fids, nomes, polys, tree = geo.load_area_polygons()
    fid_to_nome = dict(zip(fids, nomes))

    print("Carregando e normalizando fontes...")
    dfa = silver.dim_area_fm()
    occ = silver.silver_ocorrencias(tree, fids, fid_to_nome)
    dd = silver.silver_disque(tree, fids, fid_to_nome)
    fat = silver.silver_fatores(tree, fids, fid_to_nome)
    cam = silver.silver_cameras(tree, fids, fid_to_nome)
    cpsr, cpsr_n = silver.agg_cpsr(tree, fids, fid_to_nome)
    dom, dom_total, dom_valid = silver.dim_dominio(tree, fids, fid_to_nome)

    dfa.to_csv(C.OUT_SILVER / "dim_area_fm.csv", index=False)
    occ.to_csv(C.OUT_SILVER / "fact_ocorrencias.csv", index=False)
    dd.to_csv(C.OUT_SILVER / "fact_disque_denuncia.csv", index=False)
    fat.to_csv(C.OUT_SILVER / "fact_fatores_urbanos.csv", index=False)
    cam.to_csv(C.OUT_SILVER / "fact_cameras.csv", index=False)
    cpsr.to_csv(C.OUT_SILVER / "agg_cpsr_area_ano.csv", index=False)
    dom.to_csv(C.OUT_SILVER / "dim_dominio_territorial.csv", index=False)

    uni = pd.concat([occ, dd, fat, cam], ignore_index=True)
    uni.to_csv(C.OUT / "fato_unificado.csv", index=False)

    # ----------------------------------------------------------------- sanity checks
    print("\n=== 1. CONTAGENS (real vs esperado) ===")
    checks = [
        ("ocorrencias", len(occ), 115354),
        ("disque cabeças", len(dd), 18003),
        ("fatores", len(fat), 2085),
        ("cameras", len(cam), 985),
        ("áreas FM", len(dfa), 8),
        ("cpsr (linhas)", cpsr_n, 23332),
        ("domínio total", dom_total, 1628),
    ]
    ok_all = True
    for label, got, exp in checks:
        flag = "✅" if got == exp else "❌"
        ok_all &= got == exp
        print(f"  {flag} {label:18s} {got} (esperado {exp})")
    print(f"  • domínio válidos no Rio: {dom_valid} (esperado ~1090)")
    print(f"  • fids áreas: {sorted(dfa['area_fm_id'])} (esperado {C.AREA_FM_IDS})")

    print("\n=== 2. GEOM_QUALITY + COBERTURA POR ÁREA ===")
    _pct_ok_bbox(occ, "ocorrencias")
    _pct_ok_bbox(dd, "disque")
    fat_vc = _pct_ok_bbox(fat, "fatores")
    _pct_ok_bbox(cam, "cameras")

    print("\n=== 3. TESTE DA INVERSÃO X/Y (fatores) ===")
    fat_fora = fat_vc.get("out_of_bbox", 0) + fat_vc.get("missing", 0)
    flag = "✅" if fat_fora == 0 else "❌"
    print(f"  {flag} fatores fora do bbox/sem geo: {fat_fora} (esperado 0 — se >0, o swap quebrou)")

    print("\n=== 4. ENCODING (disque latin-1) ===")
    sample = " ".join(dd["category"].dropna().astype(str).head(2000)) + \
             " ".join(dd["attributes_json"].dropna().astype(str).head(500))
    flag = "✅" if "�" not in sample else "❌"
    print(f"  {flag} sem caractere de replacement (�); ex. categoria: {dd['category'].dropna().iloc[0]!r}")

    print("\n=== 5. FATO UNIFICADO ===")
    soma = len(occ) + len(dd) + len(fat) + len(cam)
    flag = "✅" if len(uni) == soma else "❌"
    print(f"  {flag} linhas={len(uni)} == soma das 4 fontes ({soma})")
    print(f"  por fonte: {uni['source'].value_counts().to_dict()}")

    print("\n=== 6. TOTAL POR ÁREA FM (fato unificado) ===")
    por_area = uni[uni["area_fm_id"].notna()].groupby(["area_fm_id", "source"]).size().unstack(fill_value=0)
    print(por_area.to_string())

    print("\nArquivos gravados em", C.OUT)


if __name__ == "__main__":
    main()
