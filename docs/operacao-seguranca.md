# Operação & Segurança — CompStat Rio

**Para quê:** procedimentos de rotina e de incidente. Tudo aqui assume
operação em rede interna controlada (sem login — ver
[`proximas_ideias.MD#3`](../proximas_ideias.MD)).

---

## 1. Rotação da chave Anthropic

**Cadência mínima:** trimestral (ou imediatamente em caso de vazamento
suspeito).

**Passos:**

1. Gerar nova chave em `console.anthropic.com` na conta da Prefeitura.
   Marcar a chave com `compstat-rio-YYYYMM`.
2. Atualizar `.env` (ou cofre do orquestrador) com a nova chave.
3. **Não fazer commit do .env** — confirmar `git status` antes de
   qualquer push.
4. Restart do backend: `docker compose restart backend` (ou
   `uvicorn` recarregado).
5. Verificar `/api/health`: `has_api_key=true` continua.
6. Smoke test: 1 chamada ao copiloto numa área de baixa demanda. Confere
   linha em `copilot_eventos` com `tokens_in > 0`.
7. **Revogar a chave antiga** no console Anthropic apenas após o smoke
   passar.
8. Registrar a troca em `docs/governanca.md` (próxima ata).

**Não fazer:** rotacionar sem smoke test. Não há tempo de "ambas chaves
válidas" longo na conta Prefeitura.

---

## 2. Expurgo de CSVs brutos do histórico Git

**Quando:** se um colaborador commitou um CSV de `dados/` por engano
(ignorado pelo `.gitignore` desde o commit `c0d9e21`, mas é fácil
adicionar com `git add -f`).

**Verificar:**

```bash
git log --all --diff-filter=A --name-only -- 'dados/*.csv' | head -50
git log --all --diff-filter=A --name-only -- 'dados_normalizados/silver/*.csv'
```

Os silver/dados de exemplo que **estão** versionados (Fase 1) são
esperados:

- `dados/chamados_1746_amostra.csv` — 15 chamados públicos, sem PII.
- `dados_normalizados/silver/fact_chamados_1746.csv` — silver derivado.
- Outros silver pré-existentes (commits anteriores à Fase 0).

**Qualquer arquivo de `dados/` com PII em commit recente é o alvo.**

**Procedimento (destrutivo — exige coordenação):**

1. Avisar todo colaborador para parar de commitar e fazer push do
   trabalho pendente.
2. Backup local de `.git/` antes de qualquer operação.
3. Usar `git filter-repo` (NÃO `git filter-branch`):

   ```bash
   git filter-repo --path 'dados/arquivo_indevido.csv' --invert-paths
   ```
4. Force-push para a branch principal (única vez justificada — ver
   regra em [`AGENTS.md`](../AGENTS.md) ou política do repo).
5. Todo colaborador re-clona (não basta `pull`).
6. Considera o token GitHub Personal Access Token do autor original:
   se ele tem acesso ao histórico em cache, considerar revogação.

**Anti-recorrência:** revisar `.gitignore` em cada PR; adicionar
`pre-commit` que rejeita `dados/*.csv` sem `--force-add`.

---

## 3. Kill switch da IA (incidente)

**Quando ligar:**

- Suspeita de chave vazada.
- Output do copiloto contendo PII (regressão da Tarefa 3.4).
- Custo escapou (já tem `OrcamentoExcedido` automático na Fase 3, mas o
  kill é mais agressivo).
- Pedido do gestor central.

**Como:** definir env var no processo do backend:

```bash
COMPSTAT_AI_KILL_SWITCH=1 docker compose up -d backend
# OU em prod com systemd:
systemctl set-environment COMPSTAT_AI_KILL_SWITCH=1
systemctl restart compstat-backend
```

A partir desse momento, `stream_chat` emite mensagem amigável de IA
indisponível e o restante do app (dados, mapa, plano de ação) continua
funcionando normalmente.

**Como desligar:** remover/desativar a env var + restart.

---

## 4. Resposta a incidente (chave vazada)

**Janela alvo: < 30 minutos do desconfio à mitigação.**

1. **Kill switch ON** (passo 3 acima).
2. **Revogar a chave vazada** no console Anthropic.
3. **Gerar nova chave** + atualizar `.env` (passo 1, mas sem smoke
   ainda — kill continua ligado).
4. Restart do backend para carregar a nova chave.
5. **Auditoria de uso** em `copilot_eventos`:

   ```sql
   SELECT usuario, COUNT(*), SUM(tokens_in + tokens_out), SUM(custo_usd)
   FROM copilot_eventos
   WHERE registrado_em >= datetime('now','-7 days')
   GROUP BY usuario
   ORDER BY 4 DESC;
   ```

   Picos de uso por IP/usuário desconhecido = candidatos a abuso.
6. Se a auditoria está limpa: **kill switch OFF**, smoke test (passo 1),
   incidente fechado.
7. Se há uso suspeito: manter kill ligado, escalar para a área de
   segurança da Prefeitura.

---

## 5. Backup do SQLite

**Cadência:** diária (durante o piloto), semanal depois.

```bash
# A qualquer momento (SQLite suporta backup online):
sqlite3 compstat.db ".backup compstat-$(date +%Y%m%d).db.bak"
```

**Retenção:** 30 dias diários + 12 semanais. Antes de migrar para
Postgres (futuro), o backup serve de fallback.

**O que NÃO entra no backup público:**

- `copilot_eventos` se a equipe decidir tratar custos como
  confidencial (na dúvida, sim — soma de custos por usuário pode
  expor padrões de uso).

---

## 6. Monitoração mínima

Sem Grafana/Datadog até a infra subir. Por enquanto:

- **`/api/health`** — verifica que o app subiu + tem chave.
- **`/api/health/data`** — frescor dos datasets (status verde/âmbar/
  vermelho). Frontend já mostra na Home (Tarefa 5.2).
- **Log JSON em stdout** — `compstat.req` (middleware) +
  `compstat.jobs` (scheduler). Redirecionar para arquivo:

  ```bash
  uvicorn app.backend.main:app 2>&1 | tee -a logs/compstat-$(date +%Y%m%d).log
  ```

Quando entrar Loki/CloudWatch, basta apontar o coletor para esse stdout.

---

## Histórico

| Versão | Data | Mudança |
|---|---|---|
| 1.0 | 2026-05-25 | Documento inicial (Fase 5 do plano de produtização) |
