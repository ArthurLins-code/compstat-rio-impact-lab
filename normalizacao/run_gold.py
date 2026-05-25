"""Onda 3 — gera a camada gold (area_brief + tabelas longas) e os entregáveis de entendimento."""
from . import config as C
from . import export, gold


def main():
    C.OUT_GOLD.mkdir(parents=True, exist_ok=True)
    brief, tem_dinamica = gold.build_gold()
    xlsx = export.build_xlsx()
    md = export.build_modelo_md()

    print("=== GOLD ===")
    print(f"  area_brief: {len(brief)} áreas | dinâmica do LLM incluída: {tem_dinamica}")
    cols = ["area_fm_id", "nome_area", "total_ocorrencias", "ranking_ocorrencias",
            "n_disque", "n_cameras", "n_psr_cpsr", "pico_dia_semana", "pico_hora"]
    print(brief[cols].to_string(index=False))
    print("\n=== ENTREGÁVEIS ===")
    print("  XLSX:", xlsx)
    print("  MD  :", md)


if __name__ == "__main__":
    main()
