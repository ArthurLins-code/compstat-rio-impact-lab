# Spec — Fase 1 — Cobertura de Dados Aceitável

**Objetivo:** o relatório deixa de mentir o período, passa a mostrar variação
mensal e ganha o 1746 como fonte adicional de fatores urbanos.

**Critério de sucesso (verificável):**
1. `GET /api/report/{id}?periodo=ultimos_90d` devolve `periodo.de`/`periodo.ate`
   alinhados ao recorte e os totais (`roubos`, `total`, `distribuicao`,
   matriz temporal) recalculados sobre esse recorte.
2. `indicadores.variacaoPct` deixa de ser `None` no payload do relatório.
3. Existe um carregador `normalizacao/ingest_1746.py` que (i) puxa do BigQuery
   público quando há credencial e (ii) cai num CSV-snapshot versionado em
   `dados_normalizados/silver/fact_chamados_1746.csv` quando não há.
4. Os chamados do 1746 entram no agregado de fatores urbanos consumido pelo
   match e pelo Plano de Ação (sem reestruturar o gold).

---

## Premissa de tempo (importante)

`fact_ocorrencias` traz `ano/mes/hora/dia_semana` — a coluna `data` original
é "lixo" (datas falsas), conforme [`MODELO_DE_DADOS.md`](../../../dados_normalizados/MODELO_DE_DADOS.md).
A maior granularidade temporal confiável é **(ano, mês)**.

Os presets "últimos 30/90/180 dias" são portanto **traduzidos para meses**
(1 / 3 / 6 meses) sobre o mês mais recente disponível em `fact_ocorrencias`.
O nome de preset preserva a linguagem de gestor; a implementação opera em
janelas mensais.

---

## Tarefa 1.1 — Período relativo configurável

**Arquivos:**
- `app/backend/report/periodo.py` *(novo)* — resolve preset → janela (`ano,mes`).
- `app/backend/report/assembler.py` — recebe `Periodo` em `montar_relatorio`.
- `app/backend/report/sections.py` — passa `periodo` para os helpers de dados.
- `app/backend/data/duck.py` — funções aceitam filtro de período opcional.
- `app/backend/routers/report.py` — aceita query `?periodo=...`.
- `app/backend/match/test_match.py` — teste puro do resolver de presets.

**Presets aceitos** (string em `?periodo=`):
- `ultimos_30d` → 1 mês
- `ultimos_90d` → 3 meses (default)
- `ultimos_180d` → 6 meses
- `ano_vigente` → de janeiro até o mês mais recente do ano mais recente nos dados
- `tudo` → de min(ano,mes) a max(ano,mes) nos dados (comportamento legado)

`periodo.de`/`periodo.ate` saem no formato `"YYYY-MM"` (compatível com o
contrato atual).

**Filtro nos dados:** quando o período não é `tudo`, as funções de
`duck.py` que dependem de tempo (`indicadores`, `distribuicao_tipo`,
`matriz_temporal`) recompilam o SQL com `WHERE (ano, mes)` na janela.
Funções não-temporais (`cameras_info`, `fatores_por_orgao`, `identificacao`)
permanecem agregadas sobre todo o histórico — alterar isso entra em Fase 2
(quando vai existir versionamento).

**Risco:**
- **Baixo:** chave de cache no frontend já dispara por URL; basta a UI passar
  o preset no `fetchReport`. Sem mudança de UI nesta fase: o backend
  default (`ultimos_90d`) já melhora o estado atual.
- **Médio:** `area_brief.csv` está pré-agregado sobre todo o histórico e
  alimenta vários endpoints. Para a Fase 1, **só** sobrescrevemos os
  campos que têm semântica de período no `Relatorio` (indicadores +
  distribuição + matriz temporal). `principalFator`, `cameras`,
  `fatores_por_orgao` continuam do brief.

---

## Tarefa 1.2 — Variação mensal

**Arquivos:**
- `app/backend/data/duck.py` — `indicadores(area_id, periodo)` calcula
  `variacaoPct` comparando a janela atual com a janela imediatamente
  anterior de mesmo comprimento (ex.: últimos 90d vs 90d anteriores).

**Regra:**
- Se a janela anterior tiver 0 ocorrências → `variacaoPct = None`
  (não dividir por zero).
- Caso contrário, `variacaoPct = round((atual - anterior) / anterior * 100, 1)`.
- Se preset é `tudo`, `variacaoPct = None` (não faz sentido).

**Risco:**
- **Baixo:** semântica clara; teste puro do cálculo cobre os edge cases.

---

## Tarefa 1.3 — Ingestão do 1746

**Fonte:** `datario.administracao_servicos_publicos.chamado_1746` no BigQuery
público da Prefeitura do Rio. Subconjunto inicial: chamados com
`tipo`/`subtipo` mapeáveis a fator urbano (iluminação, poda, lixo, calçada).

**Arquivos novos:**
- `normalizacao/ingest_1746.py` — carregador. Tem dois modos:
  1. `from_bigquery(...)`: usa `google-cloud-bigquery` se houver
     `GOOGLE_APPLICATION_CREDENTIALS` ou `COMPSTAT_GCP_PROJECT`.
  2. `from_snapshot(path)`: lê CSV local (fallback determinístico para
     dev/CI).
- `dados_normalizados/silver/fact_chamados_1746.csv` — snapshot pequeno
  (amostra controlada, sem PII — 1746 não tem PII na API pública), só
  para destravar a integração até a Prefeitura habilitar billing.
- `normalizacao/mapa_1746_para_fator.py` — dicionário tipo/subtipo do 1746
  → category do esquema de fatores urbanos + órgão responsável.
- `app/backend/data/duck.py` — `fatores_por_orgao` faz UNION com os
  chamados do 1746 quando o CSV existe.

**Não-objetivos desta fase:**
- Job agendado de carga diária (Fase 5).
- Pull em produção (Fase 5, depende de billing).
- Mudança de esquema do gold (`area_brief` continua intacto — não é fonte
  para 1746 nesta fase).

**Risco:**
- **Médio:** schema do 1746 evolui — adicionar um teste de contrato que
  valida nomes de coluna esperados no snapshot.
- **Médio:** explosão de fatores (1746 tem volume grande). Filtrar por
  `status = 'fechado'` e por janela temporal compatível com a usada nas
  ocorrências antes de comitar no agregado.
- **Baixo:** sem credencial GCP, o `from_bigquery` não roda nesta máquina
  — o snapshot CSV é o caminho default neste momento.

---

## Ordem de execução

1. **Spec** (este arquivo) — commitada antes do código.
2. **Tarefa 1.1** — período no backend (sem mexer na UI).
3. **Tarefa 1.2** — variacaoPct (extensão pequena da 1.1).
4. **Tarefa 1.3** — ingestão 1746 (scaffold + snapshot + wiring no
   agregado de fatores).

Cada tarefa = 1 commit.

---

## Commits previstos

1. `docs(plano): spec da Fase 1 (período relativo, variação mensal, 1746)`
2. `feat(backend): período relativo configurável no relatório (presets)`
3. `feat(backend): preencher variacaoPct comparando janela atual vs anterior`
4. `feat(data): ingestão 1746 (BigQuery + snapshot CSV) e merge em fatores`
