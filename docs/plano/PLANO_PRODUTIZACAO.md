# Plano de Produtização — CompStat Rio

Plano para evoluir o protótipo do hackathon em um produto utilizável pela
Prefeitura do Rio de Janeiro no ciclo semanal do CompStat Municipal.

**Versão:** 2 (incorpora decisões do dia 2026-05-25)
**Fonte de verdade dos dados:** `dados_normalizados/` (silver + gold).
**Itens diferidos:** ver [`/proximas_ideias.MD`](../../proximas_ideias.MD).

---

## Princípios

1. **`dados_normalizados/` permanece como fonte de verdade.** Nenhuma fase
   reestrutura o modelo gold (`area_brief` + 3 spokes ancorados em `area_fm_id`).
2. **Decisão final é humana.** Toda saída de IA é rascunho com proveniência.
3. **LGPD por padrão.** PII nunca sai do servidor sem redator; `relato_redacted`
   bloqueado no contrato público.
4. **Spec antes de código.** Cada fase tem um arquivo em `specs/` descrevendo
   o que muda, por que e como medir sucesso.

---

## Sequenciamento

| Fase | Conteúdo | PSW | Pré-requisito |
|---|---|---:|---|
| 0 | Fundação reprodutível | 1 | — |
| 1 | Cobertura de dados aceitável (período relativo + 1746 + variação mensal) | 1.5 | Fase 0 |
| 2 | Persistência (SQLite) + workflow do Plano de Ação | 2.5 | Fase 0 |
| 3 | IA auditável (trilha + cache + PII duro + prompt registry) | 1.5 | Fase 2 |
| 4 | Frontend pronto para gestor (impressão, A11y, preditivo integrado) | 1.5 | Fase 2 |
| 5 | Operação contínua (jobs agendados + governança) | 1 | Fases 1-4 |

PSW = pessoa-semana.

---

## Fase 0 — Fundação reprodutível

**Spec:** [`specs/fase0-fundacao.md`](specs/fase0-fundacao.md)

**Resumo do escopo:**
- Eliminar caminho absoluto macOS em `normalizacao/config.py` (faz o backend
  subir em qualquer máquina).
- Consolidar dependências Python na raiz (`requirements.txt`).
- `Dockerfile` (backend) + `docker-compose.yml` para subir backend + frontend
  buildado em um comando.
- Limpar a raiz movendo entregáveis de mídia do hackathon para `docs/midia/`.
- CI mínimo (lint Python + typecheck TS + pytest do motor de match).

**Por quê:** Sem isso, nada dos próximos passos funciona em outra máquina.

**Riscos:**
- **Baixo:** o `Path()` hardcoded pode estar referenciado em script ad-hoc
  fora do repo; mitigar rodando `run_silver`/`run_gold` end-to-end e
  comparando outputs com checksum.
- **Médio:** se forem versionados artefatos pesados no `docs/midia/`, o
  clone fica lento; manter os arquivos onde já estão (Git LFS é overkill).

---

## Fase 1 — Cobertura de dados aceitável

**Spec:** [`specs/fase1-cobertura-dados.md`](specs/fase1-cobertura-dados.md)

**Escopo aprovado pelo usuário (2026-05-25):**
1. **Período relativo configurável** em `assembler.py` (presets "últimos 30/90/180
   dias", "ano vigente") via query string. Hoje o relatório mente o período
   para qualquer ciclo após 2024-12.
2. **Ingestão do 1746** (BigQuery público) como camada adicional de validação
   de fatores urbanos (iluminação, poda, lixo, calçada). Entra no bingo.
3. **Variação mensal** preenchendo `variacaoPct` (hoje `None`).

**Itens diferidos para `proximas_ideias.MD`** (vetados pelo usuário nesta fase):
- ❌ Furtos (mais difíceis de prever; sem demanda agora).
- ❌ Expansão para as 22 áreas (FM não atua sobre elas).

**Riscos:**
- **Médio:** schema do 1746 evolui; mitigar com snapshot diário e teste de
  contrato.
- **Baixo:** período relativo muda o cache do frontend; trocar `staleTime`
  por chave dependente de período.

---

## Fase 2 — Persistência + workflow do Plano de Ação

**Spec:** [`specs/fase2-persistencia.md`](specs/fase2-persistencia.md)

**Escopo aprovado:**
- **SQLite + SQLAlchemy** como banco (zero burocracia, fácil migrar para
  Postgres depois trocando uma linha). Tabelas: `relatorios`,
  `secoes_overrides`, `acoes`, `acoes_historico`, `copilot_eventos`.
- **Workflow do Plano de Ação**: transições de status
  (proposto → atribuído → em_andamento → concluído / não_resolvido),
  SLA de 90 dias, registro de evidência.
- **Histórico de versões** do relatório (diff humano × IA — alimenta o
  prompt registry da Fase 3).
- **CORS travado** em domínio do app.
- **Logging estruturado** (JSON com `request_id`, `area_id`, ação).

**Itens diferidos para `proximas_ideias.MD`:**
- ❌ Login (autenticação) — sem login simples agora.
- ❌ IdP corporativo (Gov.BR / Microsoft Entra / Keycloak).
- ❌ E-mail / notificação ao responsável nominal (responsável fica como
  órgão genérico).

**Riscos:**
- **Alto:** sem login, o backend persistido não pode ficar exposto fora de
  rede interna controlada. Documentar explicitamente como restrição
  operacional até o login chegar.
- **Médio:** migrar de `REPORT_STATE` em memória para SQLite implica
  refatorar `assembler.py`, `copilot.py` e a UI editável; usar feature-flag
  `PERSISTENT_STATE` durante a transição.

---

## Fase 3 — IA auditável

**Spec:** [`specs/fase3-ia-auditavel.md`](specs/fase3-ia-auditavel.md)

**Escopo:**
- Trilha de auditoria de cada chamada Claude (usuário, área, seção, prompt
  hash, ferramentas, tokens, custo, resposta resumida, proveniência).
- Prompt registry versionado em tabela; promoção A/B por taxa de edição
  humana (sinal vem do diff da Fase 2).
- Cache de respostas determinísticas (key = hash do `area_brief` + versão
  do prompt).
- PII: passar `attributes_json` por redator (Presidio/regex BR); teste de
  regressão garantindo que `relato_redacted` nunca chega ao frontend.
- Rate limit por usuário no copiloto; teto de custo diário com kill switch.
- Botão "reprocessar dinâmica desta área" (job assíncrono com estimativa
  de custo).

**Riscos:**
- **Médio:** cache pode mascarar dado novo; chavear no hash do brief.
- **Alto:** redação extra de PII pode esvaziar relatos do Disque; calibrar
  com a equipe antes de subir em prod.

---

## Fase 4 — Frontend pronto para gestor

**Spec:** [`specs/fase4-frontend-gestor.md`](specs/fase4-frontend-gestor.md)

**Escopo:**
- `@media print` decente em `report.css` (gestor imprime sem perder mapa).
- A11y WCAG 2.1 AA: contraste do `sev--*`, alt-text, ordem de foco.
- Aba **Mapa Preditivo** integrada ao backend (substitui iframes estáticos
  em `public/compstat/maps/*.html` por camada MapLibre dos endpoints).
- Badge de cobertura por área na Home ("dados completos / parcial").
- i18n: strings PT-BR isoladas (baixo esforço, demonstrações fora do Rio).

**Riscos:**
- **Baixo:** polimento. Risco real é depender da Fase 2 e atrasar.

---

## Fase 5 — Operação contínua + governança

**Spec:** [`specs/fase5-operacao-continua.md`](specs/fase5-operacao-continua.md)

**Escopo:**
- Job agendado (cron simples ou Prefect): carga diária do 1746, recálculo
  silver/gold, re-extração de dinâmica para áreas com novos RELINTs.
- Health checks no Home ("dados de 1746 com 36h de atraso").
- Documento de governança (1 página) em `docs/`: quem aprova promoção de
  prompt, quem fecha ação, quem revisa rascunho.
- Plano de teste em **1 área** (sugiro 20 — Presidente Vargas/Central) por
  2 ciclos antes do go-live nas 8 áreas.
- Rotação da chave Anthropic e limpeza de CSVs brutos que possam ter
  entrado por engano no histórico Git.

**Riscos:**
- **Médio:** BigQuery 1746 precisa de billing no nome da Prefeitura.
- **Baixo:** governança sem processo claro vira disputa interna.

---

## Cadência de commits

Política: 1 commit = 1 mudança coesa, com mensagem explicando **o porquê**,
não só o quê. Exemplos:
- `chore(infra): tornar BASE relativo ao repo (destrava execução fora do macOS do autor)`
- `docs: registrar plano de produtização v2 e arquivo de próximas ideias`
- `feat(backend): consolidar dependências na raiz (1 ambiente, 1 lock)`

---

## Uso de subagentes

Quando uma fase tiver trabalho **paralelizável e independente**, o agente
principal (Opus 4.7) desenha o plano e delega execução a subagentes:

- Tarefa simples/mecânica → subagente **Haiku 4.5**.
- Tarefa de raciocínio moderado → subagente **Sonnet 4.6**.
- Tarefa extremamente complexa → **Opus 4.7** também como executor.

Fase 0 é majoritariamente mecânica e linear — execução direta sem delegação
salvo para o Dockerfile, que vale um agente especializado.
