# Spec — Fase 0 — Fundação Reprodutível

**Objetivo:** fazer o sistema subir em qualquer máquina (Windows, Linux,
macOS, container) sem editar código.

**Critério de sucesso (verificável):**
1. `git clone` + `docker compose up` → backend em `:8010` e frontend em `:5173`
   respondendo, lendo os CSVs de `dados_normalizados/`.
2. Mesmo `git clone` em Windows nativo (sem Docker) + `pip install -r
   requirements.txt` + `uvicorn app.backend.main:app` → backend sobe.
3. CI roda lint + typecheck + 1 teste de match em PR.

---

## Tarefa 0.1 — Tornar `BASE` relativo ao repo

**Arquivo:** `normalizacao/config.py`

**Problema:** `BASE = Path("/Users/pedrorezende/SegurancaPublica/claude_impact_lab_compstat_rio")`
quebra qualquer execução fora da máquina do autor original. O backend importa
`normalizacao.config` (ver `app/backend/config.py:21`), então **o backend não
sobe** se este path não existir.

**Mudança proposta:**
```python
import os
from pathlib import Path

# Raiz do repositório: 1 nível acima deste arquivo (normalizacao/config.py).
# Override possível via COMPSTAT_DATA_ROOT (ex.: rodando em container).
BASE = Path(os.environ.get("COMPSTAT_DATA_ROOT", Path(__file__).resolve().parents[1]))
```

**Risco:**
- Algum script ad-hoc fora do repo pode importar `C.BASE` esperando o path
  absoluto antigo. Mitigação: documentar a env var no `README` raiz e no
  README do app.
- Em containers, montar `dados_normalizados/` em `/data` e exportar
  `COMPSTAT_DATA_ROOT=/data`.

**Teste manual:**
- `python -c "from normalizacao import config; print(config.OUT_GOLD)"` deve
  imprimir um path dentro do repo clonado.
- `python -m normalizacao.run_gold` deve ler/gravar sem erro (não estamos
  refazendo o gold, só validando que abre os arquivos).

---

## Tarefa 0.2 — Consolidar dependências na raiz

**Arquivos novos:** `requirements.txt` na raiz.
**Arquivo a manter (com nota):** `normalizacao/requirements.txt` (apenas referência).

**Conteúdo proposto (a confirmar versões):**
```
# Backend
fastapi
uvicorn[standard]
sse-starlette
pydantic
python-dotenv
anthropic
duckdb
pandas
numpy
shapely
geopandas
python-docx
openpyxl
python-multipart

# Normalização (LLM offline)
python-docx
```

**Risco:** divergência de versões entre dev e produção. Mitigação: gerar um
lock (`pip-compile` ou simplesmente `pip freeze > requirements.lock.txt`)
quando o ambiente da Prefeitura estabilizar (Fase 5).

---

## Tarefa 0.3 — Dockerfile do backend + docker-compose

**Arquivos novos:**
- `Dockerfile` (backend Python 3.11 slim + deps + uvicorn).
- `app/frontend/Dockerfile` (build Vite → nginx servindo o `dist/`).
- `docker-compose.yml` (backend, frontend, volume para `dados_normalizados/`).
- `.dockerignore`.

**Decisão:** **não** incluir Postgres no compose desta fase (Fase 2 vai usar
SQLite por decisão do usuário).

**Riscos:**
- `geopandas` em slim image às vezes pede deps de sistema (GDAL).
  Mitigação: usar `python:3.11-bookworm` e instalar `libgdal-dev`.
- Permissões de volume no Windows: testar com Docker Desktop antes de
  fechar.

---

## Tarefa 0.4 — Limpar a raiz

**Mover para `docs/midia/`:**
- `apresentacao.html`
- `apresentacaovideo` (rename para `apresentacao.mp4` se for vídeo)
- `Briefing_Hackathon_Desenvolvedores_CompStat-2.pdf`
- `CompStat_Plataforma de Inteligência.pptx - Google Slides.pdf`

**Manter na raiz:**
- `README.md`, `proximas_ideias.MD`, `.gitignore`
- `dados/`, `dados_normalizados/`, `relints/`, `sh_area_forca/`, `app/`,
  `docs/`, `normalizacao/`

**Risco:** quem tinha link direto para um PDF vai ficar com 404.
Mitigação: o README aponta para `docs/midia/` na nova localização.

---

## Tarefa 0.5 — CI mínimo

**Arquivo novo:** `.github/workflows/ci.yml`

**Pipeline:**
1. **Python** — `ruff check` + `pytest app/backend/match/test_match.py`.
2. **Frontend** — `cd app/frontend && npm ci && npm run build && tsc --noEmit`.
3. Trigger: push + PR contra `main`.

**Risco:** o teste de match pode depender de `dados_normalizados/silver/`
que está no `.gitignore`. Mitigação: usar fixtures sintéticas pequenas
em `app/backend/match/test_match.py` (se já não usa), ou comitar uma
amostra mínima sob `app/backend/match/fixtures/`.

---

## Ordem de execução

1. **Tarefa 0.1** (BASE) — destrava as outras, valida sem subir container.
2. **Tarefa 0.2** (requirements) — sem isso, Docker não constrói.
3. **Tarefa 0.4** (limpeza) — independente, faz antes do Docker pra reduzir
   contexto do build.
4. **Tarefa 0.3** (Docker) — fecha o "clone + up".
5. **Tarefa 0.5** (CI) — última, depende das anteriores estarem verdes
   localmente.

---

## Commits previstos

1. `chore(infra): tornar BASE relativo ao repo (destrava execução fora do macOS do autor)`
2. `chore(deps): consolidar requirements.txt na raiz para 1 ambiente único`
3. `chore(repo): mover entregáveis de mídia do hackathon para docs/midia`
4. `feat(infra): adicionar Dockerfile + docker-compose para subida em 1 comando`
5. `ci: lint Python + typecheck TS + teste do motor de match em PR`
