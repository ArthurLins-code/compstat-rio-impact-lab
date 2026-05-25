"""Onda 2 — extrai a dinâmica criminal dos textos (RELINTs + Disque) via Claude.

Sem ANTHROPIC_API_KEY faz um DRY-RUN: mostra o que seria processado, sem chamar a API.
Com a chave: extrai, valida citações e grava silver/dinamica_extraida.csv de forma
INCREMENTAL (salva a cada unidade) com progresso visível e resiliência a falhas isoladas.
"""
import os

import pandas as pd

from . import config as C
from .llm import extract as E
from .llm import prompts as P
from .llm import schema as S


def main():
    areas = pd.read_csv(C.OUT_SILVER / "dim_area_fm.csv")
    relint_units = E.ler_relints(areas)
    disque_lotes = E.preparar_disque(areas)

    n_docs = len({u["doc_id"] for u in relint_units})
    n_relatos = sum(len(lote["relatos"]) for lote in disque_lotes)
    print(f"RELINT: {len(relint_units)} unidades de {n_docs} documentos")
    print(f"Disque: {len(disque_lotes)} lotes, {n_relatos} relatos (teto {E.MAX_RELATOS_POR_AREA}/área)")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n[DRY-RUN] ANTHROPIC_API_KEY ausente — extração não executada.")
        print("Exporte a chave e rode  .venv/bin/python -m normalizacao.run_llm")
        return

    # tarefas unificadas (cada uma vira uma chamada ao Claude)
    tarefas = [("RELINT", u) for u in relint_units] + [
        ("DISQUE_DENUNCIA", lote) for lote in disque_lotes
    ]
    total = len(tarefas)
    out_path = C.OUT_SILVER / "dinamica_extraida.csv"

    rows, tot_c, val_c, falhas = [], 0, 0, []
    print(f"\nExtraindo {total} unidades (modelo {E.MODEL})...", flush=True)
    for i, (tipo, item) in enumerate(tarefas, 1):
        rotulo = f"{item['doc_id']} {item.get('sub_local') or ''}".strip()
        print(f"  [{i:>2}/{total}] {tipo:16s} {rotulo}", flush=True)
        try:
            if tipo == "RELINT":
                texto = item["texto"]
                d = E.call_claude(P.user_relint(item["nome_area"], item["sub_local"] or "ABERTURA", texto))
                d.sub_local = item["sub_local"]
            else:
                texto = "\n".join(item["relatos"])
                d = E.call_claude(P.user_disque(item["nome_area"], item["relatos"]))
            t, v = E.filtrar_citacoes(d, texto)
            tot_c, val_c = tot_c + t, val_c + v
            rows += S.explode(d, item["area_fm_id"], item["doc_id"], tipo)
            pd.DataFrame(rows).to_csv(out_path, index=False)  # salvamento incremental
        except Exception as ex:
            falhas.append((item["doc_id"], item.get("sub_local"), str(ex)[:140]))
            print(f"        FALHOU: {str(ex)[:120]}", flush=True)

    print(f"\n✅ dinamica_extraida.csv: {len(rows)} linhas | citações válidas: {val_c}/{tot_c}")
    if rows:
        out = pd.DataFrame(rows)
        ausentes = out[out["declarado_ausente"]]["campo"].value_counts().to_dict()
        print(f"   campos declarados ausentes: {ausentes}")
    if falhas:
        print(f"⚠️ {len(falhas)} unidades falharam (puladas):")
        for doc, sub, err in falhas:
            print(f"   - {doc} {sub or ''}: {err}")


if __name__ == "__main__":
    main()
