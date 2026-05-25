# Spec — Fase 4 — Frontend Pronto para Gestor

**Objetivo:** o frontend para de "demonstrar" e passa a entregar o relatório
em condições que o gestor leva para a reunião do CompStat — impressão
decente, contraste WCAG, mapa preditivo plugado nos dados do backend, sinal
honesto de cobertura de dados, e strings prontas para futura tradução.

**Critério de sucesso:**
1. `Ctrl+P` em qualquer relatório gera PDF A4 legível: copiloto e nav
   ocultos, cabeçalho/rodapé identificando área + período, sem cortes
   abruptos em cartões.
2. Auditoria axe-core (manual) sobre `/home` e relatório não levanta
   nenhum erro WCAG 2.1 AA — contraste, ordem de foco, alt-text.
3. Aba "Mapa Preditivo" tem novo modo "Ao vivo" alimentado por
   `GET /api/areas/{id}/predictive`; iframes estáticos permanecem como
   "Modelo oficial".
4. Cada `AreaCard` mostra badge de cobertura (`Completos` / `Parcial` /
   `Indisponíveis`) derivado de campos vazios no `AreaResumo`.
5. Todas as strings PT-BR de componentes vivem em
   `app/frontend/src/i18n/pt-BR.ts` — substituição por outro idioma
   exige apenas duplicar o dicionário (preparação, não tradução
   completa).

---

## Tarefa 4.1 — Estilos de impressão (`@media print`)

**Arquivo:** `app/frontend/src/styles/print.css` *(novo)*, importado em `main.tsx`.

**Regras:**
- Esconde `.shell__nav`, `.shell__copilot`, `.topbar`, botões e qualquer
  CTA. `display: none !important;` em chips de UI/edição.
- Força fundo branco + texto preto-quase-preto (contraste de impressão).
- `page-break-inside: avoid;` em `.section-card` para não cortar.
- Quebra de página antes de seções "grandes" (mapa, plano de ação).
- Cabeçalho de página: `@page { size: A4; margin: 14mm; }` com regras de
  primeira página exibindo nome da área + período.

**Risco:** mapas (canvas WebGL) não imprimem por padrão. Mitigação:
`onbeforeprint` força repaint e mostra placeholder rasterizado quando
possível; documenta no spec que mapas ficam em branco em browsers que
não suportam canvas no PDF — operador imprime "Resumo executivo" sem mapa.

---

## Tarefa 4.2 — Acessibilidade WCAG 2.1 AA

**Mudanças mínimas (sem reescrever UI):**
- Substituir `--sev-*-text` por tons que atingem 4.5:1 contra
  `--sev-*-soft` (medir com WebAIM). `tokens.css` ganha override
  comentado.
- `outline-offset` + `outline: 3px solid var(--primary-ring)` em todos
  os `*:focus-visible` (já existe na maioria; sweeper em
  `components.css`).
- `<button>` sem texto visível ganha `aria-label`.
- `<svg>` decorativo tem `aria-hidden="true"`; com significado tem
  `<title>` ou `role="img"` + `aria-label`.
- Ordem de foco do top-bar segue a leitura visual (logo → seletor →
  copiloto).

**Risco:** baixo. É polimento + testes manuais com Tab e leitor de tela.

---

## Tarefa 4.3 — Mapa Preditivo "Ao vivo"

**Backend novo:** `GET /api/areas/{area_id}/predictive` devolve:
```json
{
  "areaId": 20,
  "scoreArea": 8.2,
  "hexagonos": [
    {"lat": -22.91, "lon": -43.17, "score": 0.92, "n_ocorrencias": 14, "camadas": ["mancha","fator"]}
  ]
}
```
Reusa `compute_match` e expõe as coincidências em formato de "hexágono"
(aqui, apenas pontos com score; H3 real entra no follow-up).

**Frontend:**
- `predictive/PredictiveMapPanel.tsx` ganha toggle:
  - **Oficial** (default): iframes estáticos atuais.
  - **Ao vivo**: novo componente `PredictiveMapLive.tsx` usando
    MapLibre (reusa o basemap de `HotspotMap.tsx`) + camada de
    círculos coloridos por score.
- Documenta que o modo "Ao vivo" reflete o estado atual dos dados do
  CompStat — atualizado sempre que o gold roda.

---

## Tarefa 4.4 — Badge de cobertura por área (Home)

**Regra:**
- `Completos`: tem `picoDiaSemana`, `picoHora`, `principalFator` e
  `nDisque > 0`.
- `Parcial`: faltam ≥1 desses sinais.
- `Indisponíveis`: `totalOcorrencias === 0`.

Componente `CoverageBadge.tsx` reutilizado no `AreaCard`. Texto +
ícone (nunca cor isolada — princípio WCAG 4.2).

---

## Tarefa 4.5 — i18n: strings PT-BR isoladas

**Arquivos novos:**
- `app/frontend/src/i18n/pt-BR.ts` — dicionário plano `{chave: texto}`.
- `app/frontend/src/i18n/index.ts` — `t(chave)` lê de `pt-BR` (única
  língua ativa; estrutura pronta para `en-US`/`es-ES` no follow-up).

Refatoração inicial cobre apenas `HomePage`, `AreaCard` e
`CoverageBadge` (não vai reescrever 60 componentes nesta fase — o
critério é "estrutura pronta", não "100% traduzido").

---

## Não-objetivos

- Traduzir o app inteiro (apenas estrutura pronta nesta fase).
- Geração real de PDF server-side (browser `Ctrl+P` é suficiente).
- Migrar para H3 hexágonos reais no preditivo (entra como follow-up).
- Refatorar UI de seções para reaccount A11y — fica para uma Fase 4.6
  se o axe-core detectar problemas além dos da Tarefa 4.2.

---

## Commits previstos

1. `docs(plano): spec da Fase 4 (frontend para gestor)`
2. `feat(frontend): @media print decente para reunião do CompStat`
3. `fix(frontend): contraste e foco visível WCAG 2.1 AA (tokens + sweeper)`
4. `feat(frontend): aba Mapa Preditivo com modo "Ao vivo" plugado no backend`
5. `feat(frontend): badge de cobertura por área na Home`
6. `feat(frontend): dicionário PT-BR isolado (estrutura pronta para i18n)`
