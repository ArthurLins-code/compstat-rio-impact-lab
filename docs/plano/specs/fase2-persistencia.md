# Spec — Fase 2 — Persistência + Workflow do Plano de Ação

**Objetivo:** o estado do relatório (edições humanas, ações, snapshots) deixa
de morar em RAM e passa a sobreviver a reinício. O Plano de Ação ganha
status com transições válidas, SLA e histórico auditável.

**Critério de sucesso (verificável):**
1. Subir o backend, editar uma seção via PATCH, **reiniciar**, e a edição
   continuar lá (com `COMPSTAT_PERSISTENT_STATE=1`).
2. Criar ação, mover por todos os status (proposto → atribuído → em_andamento
   → concluído), e o histórico devolver as 3 transições com timestamp e
   ator (placeholder até existir login na backlog).
3. Cada edição via PATCH gera uma nova versão em `relatorios_versoes` com
   o diff `humano × IA` separado por origem (autor `humano` vs `ia`).
4. CORS aceita apenas `CORS_ORIGINS` da env (sem `*`); requisições com
   `Origin` divergente são rejeitadas.
5. Cada requisição registra log JSON com `request_id`, `area_id` (quando
   houver), método, path, duração e status HTTP.

---

## Premissa de segurança

Sem login, o backend persistido **não pode ser exposto fora de rede
interna controlada** — documentado em `proximas_ideias.MD#3`. O
`PERSISTENT_STATE=1` deve ser ativado apenas quando o operador entender
essa restrição.

Enquanto o flag estiver desligado (default em dev), o comportamento
permanece em memória (compatível com o de hoje).

---

## Tarefa 2.1 — Setup do banco (SQLAlchemy + SQLite)

**Arquivos novos:**
- `app/backend/db/__init__.py` — `engine`, `SessionLocal`, `get_session()`
  (context manager), `init_db()` (cria as tabelas se faltarem).
- `app/backend/db/models.py` — modelos ORM: `Relatorio`, `RelatorioVersao`,
  `SecaoOverride`, `Acao`, `AcaoHistorico`, `CopilotEvento`.

**Arquivos alterados:**
- `requirements.txt` — adiciona `sqlalchemy>=2.0`.
- `app/backend/main.py` — chama `init_db()` no `@app.on_event("startup")`
  quando o flag está ligado.
- `app/backend/config.py` — expõe `PERSISTENT_STATE: bool` (do env
  `COMPSTAT_PERSISTENT_STATE`) e `DB_URL` (default
  `sqlite:///./compstat.db`).
- `.gitignore` — adiciona `*.db` e `*.db-journal`.

**Por quê:** sem essa fundação as próximas tarefas não funcionam. O flag
permite migração progressiva sem quebrar quem já roda em memória.

**Risco:** SQLite com 1 writer + N readers atende o volume CompStat
(milhares de ações/dia no pior caso); migrar para Postgres na Fase 5
troca uma URL.

---

## Tarefa 2.2 — Overrides de seção em SQLite

**Arquivos alterados:**
- `app/backend/report/assembler.py` — `aplicar_edicao` e `get_relatorio`
  passam pelo backend (`memoria` ou `sqlite`) escolhido por flag.
- `app/backend/db/overrides.py` *(novo)* — `salvar(area_id, secao, payload,
  autor)` e `carregar(area_id) -> dict`.

**Modelo:**
```
SecaoOverride(
  area_id INTEGER NOT NULL,
  secao   TEXT    NOT NULL,
  payload JSON    NOT NULL,
  autor   TEXT    NOT NULL DEFAULT 'humano',  -- 'humano' | 'ia'
  atualizado_em TIMESTAMP NOT NULL,
  PRIMARY KEY (area_id, secao)
)
```

`autor` distingue edição vinda do gestor (PATCH direto) vs do copiloto
(via `/apply`). Alimenta o diff humano×IA da Tarefa 2.4.

---

## Tarefa 2.3 — Plano de Ação com workflow

**Modelos:**
```
Acao(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  area_id INTEGER NOT NULL,
  origem_acao_id TEXT,        -- id da AcaoRow gerada por sec_plano_acao
  acao TEXT NOT NULL,
  responsavel TEXT,            -- órgão (Comlurb, RioLuz, ...)
  status TEXT NOT NULL,        -- proposto|atribuido|em_andamento|concluido|nao_resolvido
  prazo DATE,                  -- default: criada_em + 90 dias
  evidencia TEXT,              -- texto livre / URL
  criada_em TIMESTAMP NOT NULL,
  atualizada_em TIMESTAMP NOT NULL
)

AcaoHistorico(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  acao_id INTEGER NOT NULL REFERENCES acoes(id),
  de_status TEXT,
  para_status TEXT NOT NULL,
  ator TEXT NOT NULL DEFAULT 'anonimo',
  observacao TEXT,
  registrado_em TIMESTAMP NOT NULL
)
```

**Transições válidas:**
```
proposto    -> atribuido | nao_resolvido
atribuido   -> em_andamento | nao_resolvido
em_andamento -> concluido | nao_resolvido
concluido   -> em_andamento   (reabrir)
nao_resolvido -> atribuido    (reabrir)
```

Outras transições levantam `HTTPException(400)`.

**Endpoints novos:**
- `GET    /api/areas/{area_id}/acoes?status=...` — lista.
- `POST   /api/areas/{area_id}/acoes` — cria (status inicial `proposto`,
  prazo default +90d).
- `PATCH  /api/acoes/{id}` — atualiza campo. Mudança de status valida
  transição e grava `AcaoHistorico`.
- `GET    /api/acoes/{id}/historico` — devolve o histórico ordenado.

**Seed automático:** na primeira leitura de `GET /areas/{id}/acoes` com a
tabela vazia, popula com as ações derivadas de `sec_plano_acao(area_id)`.
Idempotente (chave `origem_acao_id`).

---

## Tarefa 2.4 — Histórico de versões do relatório

**Modelo:**
```
RelatorioVersao(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  area_id INTEGER NOT NULL,
  versao INTEGER NOT NULL,        -- 1, 2, 3, ... por area_id
  origem TEXT NOT NULL,           -- 'humano' | 'ia'
  snapshot JSON NOT NULL,         -- payload completo do relatório
  diff_texto TEXT,                -- resumo legível (não estrutural)
  criado_em TIMESTAMP NOT NULL,
  UNIQUE (area_id, versao)
)
```

**Hook de versão:** `aplicar_edicao` chama `db.versoes.snapshot(area_id,
origem)` após gravar override. Origem vem do parâmetro `autor` da
Tarefa 2.2.

**Endpoint novo:** `GET /api/report/{id}/versoes` — lista metadados (sem
snapshot, para não inflar payload).

**Diff humano×IA:** comparar duas versões consecutivas pelas seções
mudadas. Sinal serve à Fase 3 (promoção de prompt por taxa de edição).

---

## Tarefa 2.5 — CORS travado + logging estruturado

**Mudança CORS:** `config.CORS_ORIGINS` proibido conter `"*"` quando
`PERSISTENT_STATE=1`. Levanta erro de startup com mensagem clara.

**Middleware de logging:**
- `app/backend/middleware/logging.py` *(novo)* — gera `request_id`
  (uuid4), extrai `area_id` do path quando possível, mede duração, emite
  JSON em `logging.getLogger("compstat.req")`.
- Resposta carrega header `X-Request-ID` para correlação cliente↔server.

**Formato do log:**
```json
{"ts":"2026-05-25T14:21:00Z","level":"INFO","logger":"compstat.req",
 "request_id":"...","method":"PATCH","path":"/api/report/20/section/...",
 "area_id":20,"status":200,"duration_ms":47}
```

---

## Não-objetivos desta fase (vetados em 2026-05-25)

- Login / autenticação (item #3 de `proximas_ideias.MD`).
- IdP corporativo (Gov.BR / Microsoft Entra / Keycloak).
- Notificação por e-mail/canal direto (item #4 de `proximas_ideias.MD`).
- Migração para Postgres (Fase 5).

A persistência **não pode** ser exposta publicamente nesta fase. Documentar
explicitamente na seção de operação do README quando for o caso.

---

## Ordem de execução

1. **Spec** (este arquivo).
2. **2.1** — Scaffold do DB.
3. **2.2** — Overrides em SQLite (com flag).
4. **2.3** — Plano de Ação + workflow + histórico.
5. **2.4** — Versões do relatório.
6. **2.5** — CORS travado + logging estruturado.

Cada tarefa = 1 commit. Total previsto: 6 commits.

---

## Commits previstos

1. `docs(plano): spec da Fase 2 (SQLite + workflow + governança operacional)`
2. `feat(db): scaffold SQLAlchemy + modelos (flag PERSISTENT_STATE)`
3. `feat(backend): overrides de seção em SQLite (mantém memória como fallback)`
4. `feat(acoes): Plano de Ação com workflow, SLA 90d e histórico`
5. `feat(relatorios): versões persistidas + diff humano x IA`
6. `feat(infra): CORS travado + logging JSON estruturado por requisição`
