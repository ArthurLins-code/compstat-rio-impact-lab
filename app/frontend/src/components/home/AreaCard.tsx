// Card de área da página inicial. Layout executivo denso: ranking + faixa de
// urgência, KPI de ocorrências, indicadores de apoio, pico e principal fator.
import { AREAS_FM } from '../../api/types'
import type { AreaResumo } from '../../api/types'
import { t } from '../../i18n'
import { CoverageBadge } from './CoverageBadge'

const nf = new Intl.NumberFormat('pt-BR')

/** Faixa de urgência a partir do ranking (1 = mais urgente, 8 áreas no total). */
function urgencia(ranking: number): { cls: string; label: string } {
  if (ranking <= 3) return { cls: 'sev--alta', label: t('sev.alta') }
  if (ranking <= 6) return { cls: 'sev--media', label: t('sev.media') }
  return { cls: 'sev--baixa', label: t('sev.baixa') }
}

export function AreaCard({
  area,
  onSelect,
}: {
  area: AreaResumo
  onSelect: (id: number) => void
}) {
  const nome = AREAS_FM[area.areaId] ?? area.nomeArea
  const urg = urgencia(area.ranking)
  const pico =
    area.picoHora != null ? `${area.picoDiaSemana} · ${area.picoHora}h` : area.picoDiaSemana

  return (
    <button
      type="button"
      className="area-card"
      onClick={() => onSelect(area.areaId)}
      aria-label={t('area.aria-abrir', {
        nome,
        urg: urg.label,
        total: nf.format(area.totalOcorrencias),
      })}
    >
      <div className="area-card__head">
        <span className="area-card__rank">{area.ranking}º</span>
        <span className={`sev ${urg.cls} area-card__sev`}>{urg.label}</span>
        <CoverageBadge area={area} />
      </div>

      <h2 className="area-card__name">{nome}</h2>

      <div className="area-card__kpi">
        <span className="area-card__kpi-val tnum">{nf.format(area.totalOcorrencias)}</span>
        <span className="area-card__kpi-cap">{t('area.kpi-ocorrencias')}</span>
      </div>

      <div className="area-card__stats">
        <div className="area-card__stat">
          <span className="area-card__stat-val tnum">{nf.format(area.nDisque)}</span>
          <span className="area-card__stat-cap">{t('area.stat-denuncias')}</span>
        </div>
        <div className="area-card__stat">
          <span className="area-card__stat-val tnum">{nf.format(area.nCameras)}</span>
          <span className="area-card__stat-cap">{t('area.stat-cameras')}</span>
        </div>
        <div className="area-card__stat">
          <span className="area-card__stat-val tnum">{nf.format(area.nPsrCpsr)}</span>
          <span className="area-card__stat-cap">{t('area.stat-sit-rua')}</span>
        </div>
      </div>

      <dl className="area-card__meta">
        {pico && (
          <div className="area-card__meta-row">
            <dt>{t('area.meta-pico')}</dt>
            <dd>{pico}</dd>
          </div>
        )}
        {area.principalFator && (
          <div className="area-card__meta-row">
            <dt>{t('area.meta-fator')}</dt>
            <dd>{area.principalFator}</dd>
          </div>
        )}
      </dl>

      <span className="area-card__cta">
        {t('area.cta-ver')}
        <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
          <path d="M5 12h14M13 6l6 6-6 6" />
        </svg>
      </span>
    </button>
  )
}
