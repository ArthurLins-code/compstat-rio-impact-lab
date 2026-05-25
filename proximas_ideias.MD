# Próximas Ideias — Backlog Diferido

Itens explicitamente fora do escopo das fases 0-5 do
[`docs/plano/PLANO_PRODUTIZACAO.md`](docs/plano/PLANO_PRODUTIZACAO.md),
mas que valem a pena registrar para retomada futura.

Cada item tem **motivo do diferimento** e **dica de quando reabrir**.

---

## 1. Furtos como segundo crime monitorado

**Estado atual:** o dataset só cobre roubo. O briefing do hackathon pede
roubo *e* furto na Seção 3 do Relatório Analítico.

**Por que foi diferido:** furto é mais difícil de prever (alta subnotificação,
modus operacional mais variado, baixa correlação com fatores ambientais
duros). Sem demanda imediata da Força Municipal nesta frente.

**Quando reabrir:** se a Secretaria pedir, ou se aparecer uma fonte de furtos
georreferenciados com qualidade comparável à atual de roubos.

**Esforço estimado:** ~1 PSW — estender extrator de ocorrências, ajustar
`gold_ocorrencias_tipo`, separar indicadores na Seção 3 do relatório.

---

## 2. Expansão para as 22 áreas prioritárias

**Estado atual:** sistema cobre 8 das 22 áreas (as que têm polígono FM).

**Por que foi diferido:** a Força Municipal não atua sobre as outras 14 hoje.
Cobrir áreas sem operação gera ruído na priorização e expectativa que não
se cumpre.

**Quando reabrir:** quando a FM expandir operação para novas áreas e a
Prefeitura disponibilizar os polígonos correspondentes.

**Esforço estimado:** ~0.5 PSW — `AREA_FM_IDS` passa a ser lido do
shapefile; UI já tem badge de cobertura parcial (Fase 4).

---

## 3. Autenticação corporativa (IdP)

**Estado atual:** sem login. App é acessível por quem chegar à URL.

**Por que foi diferido:** decisão do usuário em 2026-05-25 — por enquanto,
manter sem login. Implica que o app **não pode ser exposto fora de rede
interna controlada** até este item ser resolvido.

**Opções a considerar quando reabrir:**
- **Gov.BR** — login federal único; bom para cidadão, overkill para
  servidor interno.
- **Microsoft Entra / Active Directory** — provável que a Prefeitura já
  use no Office 365 corporativo; menor fricção para o servidor.
- **Keycloak próprio** — flexibilidade máxima, custo de manutenção alto.

**Etapas mínimas:**
1. Login simples local (4 contas chumbadas: analista FM, gestor CompStat,
   órgão executor, auditor) com camada de abstração OIDC.
2. Trocar para o IdP escolhido sem reescrever rotas (a abstração isola).

**Esforço estimado:** 0.5 PSW (login simples) + 0.5 PSW (integração OIDC
quando o IdP for escolhido).

---

## 4. Notificação ao responsável nominal da ação (e-mail / canal direto)

**Estado atual:** Plano de Ação (Fase 2) registra responsável como **órgão
genérico** (Comlurb, RioLuz, SEOP, etc.). Não há aviso automático para a
pessoa que precisa executar.

**Por que foi diferido:** usuário aprovou começar com órgão genérico;
canal nominal é segunda iteração.

**Quando reabrir:** assim que cada órgão indicar um e-mail (ou canal) por
área de atuação. Boa estratégia para fechar o loop de execução do CompStat.

**Opções de canal:**
- **E-mail institucional** (mais simples, todos já têm).
- **Slack/Teams** se a Prefeitura adotar.
- **Webhook do SR-Urbano** (se houver API) — abre OS automaticamente
  com a ação como descrição.

**Esforço estimado:** ~1 PSW — tabela `responsaveis(orgao, area_id,
nome, email, canal)`, serviço de envio com retry, opt-out por
responsável, log no `acoes_historico` da Fase 2.

---

## Como adicionar novos itens a este arquivo

Quando uma ideia surgir mas estiver fora do escopo da fase atual:

1. Adicione uma seção numerada com **Estado atual**, **Por que foi diferido**,
   **Quando reabrir** e **Esforço estimado**.
2. Se for ideia técnica densa, linke um spec em `docs/plano/specs/` mesmo
   antes da implementação — facilita retomada.
3. Não delete itens daqui ao implementá-los — mova para a fase do plano e
   marque aqui com data e link para o commit/PR de execução.
