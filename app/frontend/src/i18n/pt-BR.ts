// Dicionário PT-BR (Tarefa 4.5).
//
// Estrutura plana: chave em kebab-case-com-namespace ("home.titulo",
// "cobertura.completos") -> texto. Traduzir para outro idioma = duplicar
// este arquivo (`en-US.ts`) e mudar `index.ts` para apontar.
//
// Cobertura inicial: HomePage + AreaCard + CoverageBadge — não vai
// reescrever 60 componentes nesta fase. O critério é estrutura pronta,
// não 100% traduzido. Outros componentes seguem com strings inline até
// uma migração focada.

export const PT_BR = {
  // Topo da Home
  'home.brand': 'CompStat Rio',
  'home.brand-sub': 'Inteligência de Segurança Pública',
  'home.cta-preditivo': 'Mapa Preditivo de Risco',
  'home.eyebrow': 'Força Municipal · Panorama operacional',
  'home.titulo': 'Áreas priorizadas por urgência',
  'home.subtitulo':
    'As {n} áreas da Força Municipal, ordenadas pelo volume de ocorrências de roubo e furto no período. Selecione uma área para abrir o relatório analítico completo.',

  // AreaCard
  'area.cta-ver': 'Ver relatório',
  'area.kpi-ocorrencias': 'ocorrências de roubo/furto',
  'area.stat-denuncias': 'denúncias',
  'area.stat-cameras': 'câmeras',
  'area.stat-sit-rua': 'pessoas em sit. de rua',
  'area.meta-pico': 'Pico',
  'area.meta-fator': 'Fator',
  'area.aria-abrir':
    'Abrir relatório de {nome} — urgência {urg}, {total} ocorrências',

  // Severidade
  'sev.alta': 'ALTA',
  'sev.media': 'MÉDIA',
  'sev.baixa': 'BAIXA',

  // Cobertura
  'cobertura.completos': 'Dados completos',
  'cobertura.parcial': 'Dados parciais',
  'cobertura.indisponiveis': 'Sem dados',
  'cobertura.completos-detalhe': 'Todos os sinais relevantes presentes',
  'cobertura.parcial-detalhe': 'Faltam: {sinais}',
  'cobertura.sinal-pico-dia': 'dia de pico',
  'cobertura.sinal-pico-hora': 'hora de pico',
  'cobertura.sinal-fator': 'fator urbano',
  'cobertura.sinal-denuncias': 'denúncias',
  'cobertura.sinal-ocorrencias': 'ocorrências',
} as const

export type ChaveI18n = keyof typeof PT_BR
