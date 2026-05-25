// Aba "Mapa Preditivo de Risco": à esquerda o mapa (iframe) com seletor de área,
// à direita o painel analítico em abas (drivers / métricas / coeficientes).
import '../../styles/predictive.css'
import { useState } from 'react'
import type { AreaMapa } from './types'
import { MAPA_GERAL, MAPAS_POR_AREA } from './predictiveMaps'
import { PredictiveMapPanel } from './PredictiveMapPanel'
import { PredictiveMapLive } from './PredictiveMapLive'
import { DriversTable } from './DriversTable'
import { ValidationMetrics } from './ValidationMetrics'
import { CoefficientsTable } from './CoefficientsTable'
import { AREAS_FM } from '../../api/types'

type Tab = 'drivers' | 'metricas' | 'coeficientes'
type Modo = 'oficial' | 'live'

const TABS: { id: Tab; label: string }[] = [
  { id: 'drivers', label: 'Drivers' },
  { id: 'metricas', label: 'Métricas' },
  { id: 'coeficientes', label: 'Coeficientes' },
]

/** Heurística simples: mapeia uma área da Força Municipal para o mapa estático
 *  que tem o nome mais parecido. Usado quando o usuário troca modo. */
function inferirAreaId(area: AreaMapa): number | undefined {
  if (area.arquivo === MAPA_GERAL.arquivo) return 20
  const nome = area.nome.toLowerCase()
  for (const [idStr, label] of Object.entries(AREAS_FM)) {
    if (label && nome.includes(label.toLowerCase().split(' ')[0])) return Number(idStr)
  }
  // Fallback: posição do arquivo na lista canônica + offset.
  const idx = MAPAS_POR_AREA.findIndex((m) => m.arquivo === area.arquivo)
  const ordem = [11, 11, 19, 10, 9, 14, 20, 2, 12]
  return idx >= 0 ? ordem[idx] : 20
}

export function MapaPreditivoPage({ onGoHome }: { onGoHome: () => void }) {
  const [selected, setSelected] = useState<AreaMapa>(MAPA_GERAL)
  const [tab, setTab] = useState<Tab>('drivers')
  const [modo, setModo] = useState<Modo>('oficial')

  const filtroArea = selected.arquivo === MAPA_GERAL.arquivo ? undefined : selected.nome
  const areaIdLive = inferirAreaId(selected) ?? 20

  return (
    <div className="pred-page">
      <header className="pred-header">
        <button type="button" className="btn btn--ghost btn--sm" onClick={onGoHome}>
          ← Panorama
        </button>
        <div className="pred-header__title">
          <strong>Mapa Preditivo de Risco</strong>
          <span className="pred-header__sub">
            {modo === 'oficial'
              ? 'Modelo logístico · horizontes T+1/T+2/T+4 · hexágonos H3'
              : 'Ao vivo · coincidências do CompStat · atualizado com o gold'}
          </span>
        </div>
        <div className="pred-mode" role="group" aria-label="Modo de visualização">
          <button
            type="button"
            className="pred-mode__btn"
            aria-pressed={modo === 'oficial' ? 'true' : 'false'}
            onClick={() => setModo('oficial')}
          >
            Modelo oficial
          </button>
          <button
            type="button"
            className="pred-mode__btn"
            aria-pressed={modo === 'live' ? 'true' : 'false'}
            onClick={() => setModo('live')}
          >
            Ao vivo
          </button>
        </div>
      </header>

      <div className="pred-layout">
        <section className="pred-map-col">
          {modo === 'oficial' ? (
            <PredictiveMapPanel selected={selected} onSelect={setSelected} />
          ) : (
            <PredictiveMapLive areaId={areaIdLive} />
          )}
        </section>

        <aside className="pred-sidebar">
          <div className="pred-tabs" role="tablist" aria-label="Painel analítico">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id ? 'true' : 'false'}
                className={`pred-tab ${tab === t.id ? 'pred-tab--active' : ''}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="pred-sidebar__body">
            {tab === 'drivers' && <DriversTable filtroArea={filtroArea} />}
            {tab === 'metricas' && <ValidationMetrics />}
            {tab === 'coeficientes' && <CoefficientsTable />}
          </div>
        </aside>
      </div>
    </div>
  )
}
