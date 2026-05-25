// Funções de API do relatório. Caem para fixtures se o fetch falhar OU se
// VITE_USE_FIXTURES==='1'. Assim a UI sempre renderiza.
import { apiGet, apiPatch, apiPost, apiUrl, FORCE_FIXTURES } from './client'
import {
  fixtureAreas,
  fixtureAreasOverview,
  fixtureMap,
  fixtureMatch,
  fixtureRelatorio,
  fixtureTemporal,
} from './fixtures'
import type { MapPackage } from './mapTypes'
import type {
  AiBlock,
  AreaInfo,
  AreaResumo,
  HealthData,
  MatchResult,
  Relatorio,
  TemporalMatrix,
} from './types'

/** Tenta o backend; em qualquer falha (ou modo fixtures) devolve o fallback. */
async function withFallback<T>(real: () => Promise<T>, fallback: () => T): Promise<T> {
  if (FORCE_FIXTURES) return fallback()
  try {
    return await real()
  } catch {
    return fallback()
  }
}

export function fetchAreas(): Promise<AreaInfo[]> {
  return withFallback(
    () => apiGet<AreaInfo[]>('/areas'),
    () => fixtureAreas,
  )
}

/** Resumo das áreas FM (ordenado por urgência) para a página inicial. */
export function fetchAreasOverview(): Promise<AreaResumo[]> {
  return withFallback(
    () => apiGet<AreaResumo[]>('/areas/overview'),
    () => fixtureAreasOverview,
  )
}

export function fetchReport(id: number): Promise<Relatorio> {
  return withFallback(
    () => apiGet<Relatorio>(`/report/${id}`),
    () => ({ ...fixtureRelatorio, areaId: id }),
  )
}

export function fetchTemporal(id: number): Promise<TemporalMatrix> {
  return withFallback(
    () => apiGet<TemporalMatrix>(`/report/${id}/temporal`),
    () => fixtureTemporal,
  )
}

export function fetchCoincidencias(id: number): Promise<MatchResult> {
  return withFallback(
    () => apiGet<MatchResult>(`/report/${id}/coincidencias`),
    () => ({ ...fixtureMatch, areaId: id }),
  )
}

export function fetchMap(id: number): Promise<MapPackage> {
  return withFallback(
    () => apiGet<MapPackage>(`/areas/${id}/map`),
    () => fixtureMap,
  )
}

/** Regenera um bloco de IA de uma seção. Sem backend, devolve um eco do bloco. */
export function regenerateSection(id: number, secao: string): Promise<AiBlock> {
  return withFallback(
    () => apiPost<AiBlock>(`/report/${id}/section/${secao}/regenerate`),
    () => ({
      blockId: `regen-${secao}`,
      sectionId: secao,
      status: 'gerado',
      text: '[Demonstração] Texto regenerado com fixtures — o backend produziria uma nova síntese aqui.',
      geradoEm: new Date().toISOString(),
      provenance: {
        rationale: 'Regeneração simulada em modo demonstração (sem backend).',
        confidence: 'media',
        sources: [{ kind: 'quantitativo', label: 'Dados da área (demonstração)', confidence: 'media' }],
      },
    }),
  )
}

/** Persiste edição de uma seção. Sem backend, apenas confirma (otimista). */
export function patchSection(id: number, secao: string, payload: unknown): Promise<{ ok: boolean }> {
  return withFallback(
    () => apiPatch<{ ok: boolean }>(`/report/${id}/section/${secao}`, payload),
    () => ({ ok: true }),
  )
}

export function exportDocxUrl(id: number): string {
  return apiUrl(`/report/${id}/export.docx`)
}

/** Frescor dos datasets críticos (Tarefa 5.2). Fallback verde quando o
 *  backend não está disponível — não deve assustar o gestor em modo demo. */
export function fetchHealthData(): Promise<HealthData> {
  return withFallback(
    () => apiGet<HealthData>('/health/data'),
    () => ({
      datasets: [],
      statusGeral: 'verde' as const,
      computadoEm: new Date().toISOString(),
    }),
  )
}
