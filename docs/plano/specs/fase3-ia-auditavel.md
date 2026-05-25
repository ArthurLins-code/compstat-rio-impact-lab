# Spec — Fase 3 — IA Auditável

**Objetivo:** cada chamada Claude é rastreável (quem, quando, com qual
prompt, custo) e governável (rate limit, kill switch). PII fica fora do
contrato público. Prompts viram artefato versionado.

**Critério de sucesso:**
1. Toda interação com `/copilot/.../chat` ou `/report/.../regenerate` cria
   uma linha em `copilot_eventos` com `tokens_in`, `tokens_out`,
   `custo_usd`, `ferramentas`, `prompt_id`+`prompt_versao` e
   `resposta_resumo`.
2. Editar `prompts_runtime.py` deixa de exigir deploy: o runtime busca o
   prompt da tabela `prompts` (com fallback para o constante).
3. Mesma área + mesmo prompt + mesmo `area_brief` (hash) reusa resposta
   anterior (cache hit retorna em <50ms, sem chamar Claude).
4. PII (CPF, telefone, e-mail, nome+sobrenome heurístico) é mascarada
   antes de o `attributes_json` ou `relato_redacted` sair do servidor.
5. Cliente recebe HTTP 429 ao exceder N requisições por minuto e HTTP 503
   quando o teto diário de custo USD é atingido.

---

## Tarefa 3.1 — Trilha de auditoria do copiloto

**Arquivos:**
- `app/backend/db/auditoria.py` *(novo)* — `registrar(evento)`,
  `consolidar(evento_id, tokens_in, tokens_out, custo, resumo)`.
- `app/backend/ai/copilot.py` — chama `registrar`/`consolidar` em torno
  do `stream_chat`.
- `app/backend/db/models.py` — `CopilotEvento` ganha `prompt_id` e
  `prompt_versao`.

Reusa a tabela `copilot_eventos` já criada na Fase 2. `usuario` fica
`"anonimo"` até existir login.

---

## Tarefa 3.2 — Prompt registry versionado

**Modelo:**
```
Prompt(
  id INTEGER PRIMARY KEY,
  nome TEXT NOT NULL,              -- 'copiloto', 'sec_resumo_executivo', ...
  versao INTEGER NOT NULL,         -- monotônico por nome
  conteudo TEXT NOT NULL,
  ativo INTEGER NOT NULL DEFAULT 1,
  criado_em TIMESTAMP NOT NULL,
  UNIQUE (nome, versao)
)
```

**Módulo:** `app/backend/db/prompts.py`
- `obter_ativo(nome) -> (versao, conteudo) | None`
- `promover(nome, conteudo) -> versao` (cria versão N+1 + desativa anteriores)
- `seed(nome, conteudo)` — idempotente, escreve v1 se não existir.

**Runtime:** `prompts_runtime.get(nome)` consulta o DB quando flag está
ligado, com fallback para o constante de Python (compat dev/offline).

Sinal para promoção A/B vem da `versoes.taxa_de_edicao_humana` (Fase 2):
se uma versão acumula >X% de edição humana, sinaliza candidato a substituir.

---

## Tarefa 3.3 — Cache de respostas determinísticas

**Modelo:**
```
RespostaCache(
  chave_hash TEXT PRIMARY KEY,     -- sha256(area_brief_json + prompt_nome + prompt_versao + secao)
  area_id INTEGER NOT NULL,
  secao TEXT NOT NULL,
  prompt_id INTEGER,
  prompt_versao INTEGER,
  conteudo JSON NOT NULL,          -- bloco de IA pronto (text + provenance)
  tokens_in INTEGER, tokens_out INTEGER, custo_usd NUMERIC(10,4),
  criado_em TIMESTAMP NOT NULL,
  ultimo_uso_em TIMESTAMP NOT NULL,
  uso_count INTEGER NOT NULL DEFAULT 1
)
```

**Módulo:** `app/backend/ai/cache.py`
- `chave(area_id, secao, prompt_nome, prompt_versao, brief_hash) -> str`
- `obter(chave)` / `salvar(chave, conteudo, custos)`.

Aplicado nos geradores de seção (resumo/dinâmica/efetivo/plano). Não no
copiloto-chat (conversa é não-determinística por desenho).

Invalidação: muda o `area_brief` → muda o hash → cache miss natural.

---

## Tarefa 3.4 — PII duro (Presidio-like, regex BR)

**Arquivos:**
- `app/backend/ai/pii.py` *(novo)* — `redact(texto)` aplica regex de:
  - CPF (`\d{3}\.?\d{3}\.?\d{3}-?\d{2}`)
  - RG (variantes UF)
  - Telefone (com/sem DDD)
  - E-mail
  - Nome+Sobrenome capitalizado (heurística leve com lista de stop-words).
- Aplicado em:
  - `duck.disque_amostra` antes do retorno.
  - `duck._tools.consultar_relatos_disque` resultado.
  - Qualquer endpoint que devolva `attributes_json`.

**Teste de regressão:** payload com CPF/telefone/e-mail/nome conhecido
não pode sair do `/api/report/.../section/...` nem do `/copilot/.../chat`.

---

## Tarefa 3.5 — Rate limit + kill switch de custo

**Arquivos:**
- `app/backend/ai/guardrails.py` *(novo)*:
  - `consumir_token(usuario_ou_ip)` — token bucket em RAM (refill 1/s,
    burst 30). Levanta `RateLimitError`.
  - `custo_diario_atual()` — soma do dia em `copilot_eventos`.
  - `verificar_orcamento()` — levanta `OrcamentoExcedido` quando ultrapassa
    `COMPSTAT_CUSTO_DIARIO_USD` (default 5.00).
  - `kill_switch_ligado()` — checa env `COMPSTAT_AI_KILL_SWITCH`.
- Router do copiloto + dos geradores integram os 3 antes de chamar Claude.

Sem login, "usuário" = IP do cliente. Documentar que isso é provisório.

---

## Tarefa 3.6 — Reprocessar dinâmica (job assíncrono)

**Endpoint:** `POST /api/areas/{id}/reprocessar-dinamica` — usa
`BackgroundTasks` do FastAPI para acionar a extração de dinâmica
(`normalizacao/run_llm.py` já existe).

Devolve `202 Accepted` com `job_id` (uuid) + `estimativa_custo_usd`
calculada a partir do nº de relints da área × custo médio histórico do
prompt de extração (lê de `copilot_eventos`).

**Não-objetivo:** orquestrador real (Celery/Prefect) — Fase 5. Aqui
basta o background task simples.

---

## Não-objetivos desta fase

- Login real (proximas_ideias.MD#3) — `usuario='anonimo'` continua.
- Migração para Postgres.
- UI de gestão do prompt registry (continua via SQL/migrations).

---

## Commits previstos

1. `docs(plano): spec da Fase 3 (auditoria, registry, cache, PII, guardrails)`
2. `feat(ai): trilha de auditoria do copiloto (CopilotEvento)`
3. `feat(ai): prompt registry versionado em SQLite`
4. `feat(ai): cache de respostas determinísticas por hash do brief`
5. `feat(ai): redação de PII (CPF/telefone/email/nome) antes do contrato público`
6. `feat(ai): rate limit, teto diário de custo e kill switch`
7. `feat(ai): reprocessar dinâmica (background task com estimativa de custo)`
