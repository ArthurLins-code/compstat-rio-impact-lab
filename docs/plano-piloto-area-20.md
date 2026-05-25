# Plano de Piloto — Área 20 (Presidente Vargas / Central)

**Para quê:** validar o CompStat Rio em produção controlada antes do
go-live nas 8 áreas. Risco se erra: gestor toma decisão operacional
ruim baseada em rascunho de IA mal-calibrado. Dois ciclos semanais na
Área 20 dão sinal suficiente sem espalhar o risco.

**Pré-requisito:** Fases 0–5 do
[`docs/plano/PLANO_PRODUTIZACAO.md`](plano/PLANO_PRODUTIZACAO.md)
implementadas; `COMPSTAT_PERSISTENT_STATE=1`; scheduler ativo.

---

## Por que Área 20

| Critério | Por que Área 20 |
|---|---|
| **Volume** | Maior número absoluto de ocorrências (Presidente Vargas + Central + Cinelândia). Sinal estatístico mais limpo. |
| **Cobertura de dados** | Tem 1746 (área central, alta demanda municipal), RELINTs frequentes, denúncias do Disque com volume. Não vai cair no caso "dados parciais". |
| **Time consolidado** | Equipe FM da área já participa do CompStat tradicional há mais tempo. Curva de aprendizagem do produto curta. |
| **Fatores urbanos diversos** | Iluminação, calçada, comércio irregular, vegetação — todos os órgãos (Rio Luz, Comlurb, SEOP, SECONSERVA, CET-Rio) aparecem no Plano de Ação. Testa o roteamento por órgão. |
| **Risco político** | Área crítica — se o produto rateia aqui primeiro, falha contida. Se sobe junto com Campo Grande (volume comparável) e quebra, escala. |

---

## Sequência

### Ciclo 1 (semana A) — Sombra do CompStat tradicional

- **Não troca nada na operação.** Equipe FM continua usando o método
  atual.
- O CompStat Rio gera o relatório em paralelo, sem ser consumido para
  decisões reais.
- **Métricas a coletar:**
  - Tempo do servidor para montar o relatório (`/api/report/20`).
  - Taxa de edição humana (`db.versoes.taxa_de_edicao_humana(20)`) por
    seção.
  - Custo Anthropic consolidado do ciclo
    (`db.auditoria.resumo_diario` × 7).
  - Cobertura de dados na Home (`/api/health/data`).

### Ciclo 2 (semana B) — Decisão híbrida

- **Equipe FM usa o relatório do CompStat Rio como insumo principal;**
  método anterior fica como fallback.
- Ações do Plano de Ação criadas via `POST /api/areas/20/acoes` —
  começa o histórico de transições.
- Comandante de área aprova o `rascunho=false` na reunião semanal.
- **Métricas adicionais:**
  - Tempo para fechar uma ação (do `proposto` ao `concluido`).
  - Quantas ações marcadas `nao_resolvido` vs `concluido`.
  - Reedições do gestor (`origem='humano'` em `relatorios_versoes`)
    por seção — se >50% em alguma seção, prompt da seção é candidato
    a reescrita.

---

## Critérios go/no-go para go-live nas 7 áreas restantes

Após o Ciclo 2, **só liberar as outras áreas se**:

| Indicador | Limite verde | Limite âmbar | Limite vermelho |
|---|---|---|---|
| Taxa de edição humana média | ≤ 30% | 30–50% | > 50% (refatorar prompt antes) |
| Custo Anthropic / ciclo | ≤ US$ 10 | US$ 10–25 | > US$ 25 (revisar cache + guardrails) |
| Tempo médio para fechar ação | ≤ 14 dias | 14–30 dias | > 30 dias (revisar SLA + canais) |
| Erros HTTP 5xx no log | ≤ 10/ciclo | 10–50 | > 50 (investigar antes de escalar) |
| Cobertura "completos" no Home | 100% (Área 20 sempre completos) | — | — |

**Verde em tudo** → libera **Campo Grande (área 11)** + **Botafogo
(área 14)** simultaneamente no Ciclo 3.

**Âmbar em qualquer indicador** → repete o Ciclo 2 com ajustes.

**Vermelho em qualquer** → para o piloto e revisa a fase correspondente
do plano.

---

## Responsáveis

- **Patrocinador:** Secretaria CompStat (decisão de seguir/parar).
- **Líder do piloto:** Engenheiro de IA do projeto.
- **Operação na ponta:** Comandante da Área 20 (FM).
- **Avaliador independente:** Gestor CompStat Central (lê as métricas
  acima sem ver o relatório — evita viés).

---

## Quando começar

**Pré-condição:** Spec da Fase 5 marcada como entregue + scheduler
ligado em homologação por ≥ 1 semana sem incidente. Início estimado:
**Ciclo seguinte à entrega da Fase 5** (rolando, depende do calendário
da Secretaria).
