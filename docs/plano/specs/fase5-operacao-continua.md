# Spec — Fase 5 — Operação Contínua + Governança

**Objetivo:** o CompStat Rio passa a rodar sozinho no dia a dia, com
alertas honestos quando a frescor dos dados cai, governança documentada
e procedimentos de incidente claros (rotação de chave, expurgo de PII).

**Critério de sucesso:**
1. Job agendado (lightweight, embutido) roda diariamente: refresh 1746
   + checagem de frescor + log JSON estruturado. Pausa via flag.
2. `GET /api/health/data` devolve idade dos datasets críticos + sinal
   verde/âmbar/vermelho por SLA (1746 ≤ 36h, gold ≤ 7d).
3. Documento de governança (`docs/governanca.md`) cobre: quem promove
   prompt, quem fecha ação, quem revisa rascunho — 1 página.
4. Plano de teste piloto (`docs/plano-piloto-area-20.md`) descreve
   2 ciclos na Área 20 (Presidente Vargas/Central) antes do go-live.
5. README de segurança operacional (`docs/operacao-seguranca.md`):
   rotação da chave Anthropic, expurgo de CSVs brutos do histórico Git,
   resposta a incidente.

---

## Tarefa 5.1 — Job agendado embutido (sem broker)

**Decisão:** scheduler simples baseado em `threading.Timer` (zero deps
novas). APScheduler/Celery/Prefect entram quando virar problema — hoje
o uso é "1 carga/dia, 1 verificação/hora" e não justifica.

**Arquivos:**
- `app/backend/jobs/scheduler.py` *(novo)* — `agendar(nome, intervalo, func)`,
  `parar()`. Roda em thread daemon; sobrevive ao processo do uvicorn.
- `app/backend/jobs/tarefas.py` *(novo)* — funções operacionais:
  - `refresh_1746()` — chama `normalizacao.ingest_1746.from_bigquery`
    quando credencial GCP existir; fallback log.
  - `checar_frescor()` — emite log com idade dos datasets.
  - `expurgar_cache_velho()` — apaga `RespostaCache` >30d sem uso.
- `app/backend/main.py` — startup agenda quando
  `COMPSTAT_SCHEDULER_ON=1`.

**Configuração:**
- `COMPSTAT_SCHEDULER_ON` (default `0`): liga/desliga o scheduler.
- `COMPSTAT_REFRESH_1746_H` (default `24`): intervalo em horas.
- `COMPSTAT_HEALTH_INTERVAL_M` (default `60`): intervalo em minutos
  para `checar_frescor`.

---

## Tarefa 5.2 — Health checks de dados (`/api/health/data`)

**Resposta:**
```json
{
  "datasets": [
    {"nome": "gold/area_brief.csv", "idade_horas": 12.4, "sla_horas": 168, "status": "verde"},
    {"nome": "silver/fact_ocorrencias.csv", "idade_horas": 70.0, "sla_horas": 168, "status": "verde"},
    {"nome": "silver/fact_chamados_1746.csv", "idade_horas": 42.0, "sla_horas": 36, "status": "ambar"}
  ],
  "status_geral": "ambar",
  "computado_em": "..."
}
```

**Frontend:** Home mostra badge global ("Dados atualizados" / "Atenção:
1746 atrasado") consumindo este endpoint via React Query. Não bloqueia
nada — sinaliza.

---

## Tarefa 5.3 — Documento de governança (1 página)

**Conteúdo (`docs/governanca.md`):**
- **Promoção de prompt** (Fase 3 / `db.prompts`): quem decide subir uma
  versão? Critério (taxa de edição humana ≤ X%, revisão).
- **Fechamento de ação** (Fase 2 / Plano de Ação): quem move
  `em_andamento → concluído`? Requer evidência?
- **Revisão de rascunho**: quem aprova o `rascunho=false` do relatório?
- **Reabertura**: quando pode-se reverter `nao_resolvido` para `atribuido`?

Cada item: papel responsável + canal de decisão + onde fica registrado.

---

## Tarefa 5.4 — Plano de teste piloto (Área 20)

**Conteúdo (`docs/plano-piloto-area-20.md`):**
- Por que Área 20 (Presidente Vargas/Central): maior volume, equipe FM
  consolidada, fatores urbanos diversos.
- Sequência: 2 ciclos semanais consecutivos antes do go-live.
- Métricas a coletar: taxa de aceitação humana das sugestões, tempo
  para fechar ação, retrabalho do gestor.
- Critérios de go/no-go para liberar as outras 7 áreas.

---

## Tarefa 5.5 — Segurança operacional

**Conteúdo (`docs/operacao-seguranca.md`):**
- **Rotação da chave Anthropic**: passo a passo (gerar nova → atualizar
  `.env` → restart → revogar antiga). Cadência mínima: trimestral.
- **Expurgo de CSVs brutos do histórico Git**: `git filter-repo` com
  glob para `dados/*.csv` indevidos. Validar com colaboradores antes.
- **Kill switch** (já existe, Fase 3): quando ligar
  `COMPSTAT_AI_KILL_SWITCH=1`.
- **Resposta a incidente**: chave vazada → kill switch + rotação
  + auditoria de uso em `copilot_eventos`.

---

## Não-objetivos

- Orquestrador externo (Celery/Prefect): entra quando o volume justificar.
- Postgres: SQLite atende; migração entra com a engenharia que vai
  operar (DBA da Prefeitura).
- Monitoração externa (Grafana, Datadog): nesta fase apenas health
  endpoint + log JSON. Coletor de log fica para o time de infra.

---

## Commits previstos

1. `docs(plano): spec da Fase 5 (operação contínua + governança)`
2. `feat(jobs): scheduler embutido + tarefas de refresh/frescor/expurgo`
3. `feat(backend): GET /api/health/data com SLA por dataset`
4. `docs(governanca): papéis, decisões e canais (1 página)`
5. `docs(piloto): plano de teste em 2 ciclos na Área 20`
6. `docs(seguranca): rotação de chave, expurgo de CSVs, resposta a incidente`
