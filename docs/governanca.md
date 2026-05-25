# Governança Operacional — CompStat Rio

**Para quê:** quando o sistema sobe em rede interna da Prefeitura, decisões
sobre prompts, ações e versionamento precisam de dono claro. Esta página
descreve papel, canal de decisão e onde a decisão fica registrada.

**Pré-requisito:** este documento pressupõe que a Fase 5 do plano está em
vigor (`COMPSTAT_PERSISTENT_STATE=1`, scheduler ativo, login ainda
pendente — ver [`proximas_ideias.MD#3`](../proximas_ideias.MD)).

---

## Decisão 1 — Promoção de prompt

**O que é:** trocar o prompt em produção para uma nova versão
(`db.prompts.promover`).

| Quem | Quando | Onde fica |
|---|---|---|
| **Engenheiro de IA** propõe; **Comandante de área (FM)** aprova | Quando a taxa de edição humana (`db.versoes.taxa_de_edicao_humana`) de uma versão fica acima de 35% por 2 ciclos consecutivos | Tabela `prompts` (audit trail completo); decisão registrada na ata semanal do CompStat |

**Critério objetivo:** A/B em 1 área por 2 ciclos antes do go-live geral.

---

## Decisão 2 — Fechamento de ação do Plano

**O que é:** mover ação de `em_andamento` para `concluido`.

| Quem | Quando | Onde fica |
|---|---|---|
| **Órgão responsável** declara via `PATCH /api/acoes/{id}` (status + evidencia) | Quando há evidência concreta (OS encerrada, foto, número de chamado 1746) | `acoes_historico` registra ator, observação e timestamp |

**Regra dura:** sem `evidencia` preenchida, gestor pode rejeitar e devolver
para `em_andamento` (transição válida pela máquina de estados). Reabertura
para `nao_resolvido` exige justificativa em `observacao`.

---

## Decisão 3 — Revisão de rascunho (rascunho → publicado)

**O que é:** o `Relatorio.rascunho` saí de `true` para `false`, fechando o
relatório do ciclo.

| Quem | Quando | Onde fica |
|---|---|---|
| **Comandante de área (FM)** + **Gestor CompStat Central** | Reunião semanal do CompStat, após análise do diff humano×IA | `relatorios_versoes` com `origem='humano'` marca a versão publicada |

**Critério mínimo:** todas as 4 perguntas norteadoras do Resumo Executivo
respondidas (sem `status='nao_gerado'`) e Plano de Ação com responsável
para cada item.

---

## Decisão 4 — Reabertura de `nao_resolvido`

**O que é:** uma ação fechada como `nao_resolvido` volta para `atribuido`.

| Quem | Quando | Onde fica |
|---|---|---|
| **Gestor CompStat Central** | Quando novo dado surge (RELINT, denúncia 1746) que muda o entendimento | `acoes_historico` com `ator='gestor_central'` + `observacao` apontando a nova evidência |

---

## Decisão 5 — Reprocessar dinâmica de uma área (custo)

**O que é:** acionar `POST /api/areas/{id}/reprocessar-dinamica`, que gera
custo Anthropic real.

| Quem | Quando | Onde fica |
|---|---|---|
| **Comandante de área** | Quando RELINTs novos chegaram ou modelo foi promovido | `copilot_eventos` registra tokens/custo; `jobs/{id}` tem `estimativaCustoUsd` antes da execução |

**Guardrail:** `verificar_orcamento` bloqueia se passou do teto diário
(`COMPSTAT_CUSTO_DIARIO_USD`, default US$ 5/dia). Subir o teto =
decisão do gestor central + registro na ata.

---

## Decisão 6 — Acionar kill switch da IA

**O que é:** `COMPSTAT_AI_KILL_SWITCH=1` desativa toda chamada Claude.

| Quem | Quando | Onde fica |
|---|---|---|
| **Qualquer pessoa de operação** (sem aprovação prévia — é interruptor de emergência) | Suspeita de chave vazada / output inadequado / incidente | Variável de ambiente do processo; registrar incidente em `docs/operacao-seguranca.md` em até 24h |

Ver `docs/operacao-seguranca.md` para o procedimento completo de incidente.

---

## Reuniões e atas

| Reunião | Frequência | Saída |
|---|---|---|
| **CompStat semanal por área** | 1× por semana, por área | Ata curta com: ações fechadas, ações reabertas, prompt promovido (se houver), incidentes |
| **CompStat Central mensal** | 1× por mês | Revisão consolidada das 8 áreas + decisões 1, 3, 4 |
| **Comitê de governança trimestral** | A cada 3 meses | Revisão dos critérios deste documento (este arquivo é vivo) |

---

## Histórico de alterações deste documento

| Versão | Data | Mudança |
|---|---|---|
| 1.0 | 2026-05-25 | Documento inicial (Fase 5 do plano de produtização) |
