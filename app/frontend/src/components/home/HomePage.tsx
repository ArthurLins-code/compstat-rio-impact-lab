// Página inicial: panorama das áreas da Força Municipal, em cards ordenados
// por urgência (volume de ocorrências). Clicar num card abre o relatório.
import { useQuery } from '@tanstack/react-query'
import { fetchAreasOverview } from '../../api/reports'
import { t } from '../../i18n'
import { AreaCard } from './AreaCard'

export function HomePage({ onSelectArea, onOpenPredictive }: { onSelectArea: (id: number) => void; onOpenPredictive: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['areas-overview'],
    queryFn: fetchAreasOverview,
    staleTime: 5 * 60 * 1000,
  })

  const areas = [...(data ?? [])].sort((a, b) => a.ranking - b.ranking)

  return (
    <div className="home">
      <header className="home__topbar">
        <span className="home__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6z" />
            <path d="M9 12l2 2 4-4" />
          </svg>
        </span>
        <div className="home__brand">
          <strong>{t('home.brand')}</strong>
          <span className="home__brand-sub">{t('home.brand-sub')}</span>
        </div>
        <button type="button" className="btn btn--primary" style={{ marginLeft: 'auto' }} onClick={onOpenPredictive}>
          {t('home.cta-preditivo')}
        </button>
      </header>

      <main className="home__body">
        <div className="home__intro">
          <span className="home__eyebrow">{t('home.eyebrow')}</span>
          <h1 className="home__title">{t('home.titulo')}</h1>
          <p className="home__subtitle">{t('home.subtitulo', { n: areas.length || 8 })}</p>
        </div>

        {isLoading ? (
          <ul className="area-grid" aria-busy="true">
            {Array.from({ length: 8 }).map((_, i) => (
              <li key={i}>
                <div className="area-card area-card--skeleton" aria-hidden="true" />
              </li>
            ))}
          </ul>
        ) : (
          <ul className="area-grid">
            {areas.map((a) => (
              <li key={a.areaId}>
                <AreaCard area={a} onSelect={onSelectArea} />
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}
