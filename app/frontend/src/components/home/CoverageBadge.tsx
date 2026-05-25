// CoverageBadge — sinal honesto da qualidade dos dados da área (Tarefa 4.4).
// Cor + ícone + rótulo (nunca cor isolada, WCAG 1.4.1). Três níveis:
//   completos    — todos os sinais relevantes presentes
//   parcial      — falta ≥1 sinal (UI informa o que falta no title)
//   indisponíveis — sem ocorrências; relatório terá pouco a dizer
import type { AreaResumo } from '../../api/types'
import { t } from '../../i18n'

export type Cobertura = 'completos' | 'parcial' | 'indisponiveis'

interface SinalAusente {
  campo: string
  rotulo: string
}

function avaliar(a: AreaResumo): { nivel: Cobertura; ausentes: SinalAusente[] } {
  if (!a.totalOcorrencias) {
    return {
      nivel: 'indisponiveis',
      ausentes: [{ campo: 'totalOcorrencias', rotulo: t('cobertura.sinal-ocorrencias') }],
    }
  }
  const ausentes: SinalAusente[] = []
  if (!a.picoDiaSemana) ausentes.push({ campo: 'picoDiaSemana', rotulo: t('cobertura.sinal-pico-dia') })
  if (a.picoHora == null) ausentes.push({ campo: 'picoHora', rotulo: t('cobertura.sinal-pico-hora') })
  if (!a.principalFator) ausentes.push({ campo: 'principalFator', rotulo: t('cobertura.sinal-fator') })
  if (!a.nDisque) ausentes.push({ campo: 'nDisque', rotulo: t('cobertura.sinal-denuncias') })
  return { nivel: ausentes.length ? 'parcial' : 'completos', ausentes }
}

const ROTULO_POR_NIVEL: Record<Cobertura, string> = {
  completos: t('cobertura.completos'),
  parcial: t('cobertura.parcial'),
  indisponiveis: t('cobertura.indisponiveis'),
}

function Icone({ nivel }: { nivel: Cobertura }) {
  // Ícones diferentes por nível (sinal redundante além da cor).
  if (nivel === 'completos') {
    return (
      <svg className="cov__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
        <path d="M20 6L9 17l-5-5" />
      </svg>
    )
  }
  if (nivel === 'parcial') {
    return (
      <svg className="cov__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8v4M12 16h.01" />
      </svg>
    )
  }
  return (
    <svg className="cov__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M9 9l6 6M15 9l-6 6" />
    </svg>
  )
}

export function CoverageBadge({ area }: { area: AreaResumo }) {
  const { nivel, ausentes } = avaliar(area)
  const titulo = ausentes.length
    ? t('cobertura.parcial-detalhe', { sinais: ausentes.map((a) => a.rotulo).join(', ') })
    : t('cobertura.completos-detalhe')
  const rotulo = ROTULO_POR_NIVEL[nivel]
  return (
    <span className={`cov cov--${nivel}`} title={titulo} aria-label={`${rotulo}. ${titulo}`}>
      <Icone nivel={nivel} />
      {rotulo}
    </span>
  )
}
