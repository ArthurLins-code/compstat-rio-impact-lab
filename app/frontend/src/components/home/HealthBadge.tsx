// HealthBadge — sinal global de frescor dos dados (Tarefa 5.2).
// Aparece no topo da Home: se algum dataset crítico está atrasado, o
// gestor sabe antes de abrir o relatório.
import type { ReactElement } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchHealthData } from '../../api/reports'
import type { StatusFrescor } from '../../api/types'

const ROTULO: Record<StatusFrescor, string> = {
  verde: 'Dados atualizados',
  ambar: 'Atenção: dados parcialmente atrasados',
  vermelho: 'Dados desatualizados',
}

const ICONE: Record<StatusFrescor, ReactElement> = {
  verde: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  ),
  ambar: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path d="M12 2L2 22h20L12 2z" />
      <path d="M12 9v4M12 17h.01" />
    </svg>
  ),
  vermelho: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M9 9l6 6M15 9l-6 6" />
    </svg>
  ),
}

export function HealthBadge() {
  const { data, isLoading } = useQuery({
    queryKey: ['health-data'],
    queryFn: fetchHealthData,
    staleTime: 5 * 60 * 1000,
  })
  if (isLoading || !data) return null
  const atrasados = data.datasets.filter((d) => d.status !== 'verde')
  const title = atrasados.length
    ? `Atrasados: ${atrasados.map((d) => `${d.nome} (${d.idadeHoras ?? '?'}h)`).join('; ')}`
    : 'Todos os datasets dentro do SLA'
  return (
    <span
      className={`health-badge health-badge--${data.statusGeral}`}
      title={title}
      aria-label={`${ROTULO[data.statusGeral]}. ${title}`}
    >
      <span className="health-badge__icon">{ICONE[data.statusGeral]}</span>
      {ROTULO[data.statusGeral]}
    </span>
  )
}
