// ReportView — orquestra o cabeçalho do relatório e as 10 seções.
import { useReport } from '../../state/reportContext'
import { SEVERITY_LABEL, severityFromScore } from '../../lib/severity'
import { S1Identificacao } from './sections/S1Identificacao'
import { S2Mapa } from './sections/S2Mapa'
import { S3ResumoExecutivo } from './sections/S3ResumoExecutivo'
import { S4Ocorrencias } from './sections/S4Ocorrencias'
import { S5Temporal } from './sections/S5Temporal'
import { S6DinamicaCriminal } from './sections/S6DinamicaCriminal'
import { S7EfetivoFM } from './sections/S7EfetivoFM'
import { S8Fatores } from './sections/S8Fatores'
import { S9Cameras } from './sections/S9Cameras'
import { S10Coincidencias } from './sections/S10Coincidencias'

function fmtDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('pt-BR')
}

export function ReportView() {
  const { report, isLoading } = useReport()

  if (isLoading || !report) {
    return (
      <div className="report-loading">
        <div className="report-loading__bar" />
        <p className="muted">Carregando relatório da área…</p>
      </div>
    )
  }

  const sev = severityFromScore(report.coincidencias?.scoreArea)
  const ind = report.ocorrencias.indicadores
  const trechos = report.identificacao.trechosCriticos

  return (
    <div className="report">
      {/* Cabeçalho visível só na impressão (Tarefa 4.1): identifica a folha. */}
      <header data-print-cover>
        <h1>
          Área {String(report.areaId).padStart(2, '0')} — {report.nomeArea}
        </h1>
        <div className="print-period">
          Período: {fmtDate(report.periodo.de)} – {fmtDate(report.periodo.ate)} ·{' '}
          {ind.total.toLocaleString('pt-BR')} ocorrências · Severidade {SEVERITY_LABEL[sev]}
        </div>
      </header>

      <header className="report__header">
        <div className="report__heading">
          <span className="report__eyebrow">Relatório Analítico de Área · CompStat Municipal</span>
          <h1 className="report__title">
            Área {String(report.areaId).padStart(2, '0')} — {report.nomeArea}
          </h1>
        </div>

        <div className="report__status" role="group" aria-label="Resumo operacional da área">
          <span className={`sev sev--${sev}`}>
            <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
            Severidade {SEVERITY_LABEL[sev]}
          </span>
          <span className="report__stat">
            <span className="report__stat-val mono">
              {fmtDate(report.periodo.de)} – {fmtDate(report.periodo.ate)}
            </span>
            <span className="report__stat-cap">Período de referência</span>
          </span>
          <span className="report__stat">
            <span className="report__stat-val mono">{ind.total.toLocaleString('pt-BR')}</span>
            <span className="report__stat-cap">Ocorrências</span>
          </span>
          <span className="report__stat">
            <span className="report__stat-val mono">{ind.rankingEntreAreas}º</span>
            <span className="report__stat-cap">Ranking entre áreas</span>
          </span>
          {typeof trechos === 'number' && (
            <span className="report__stat">
              <span className="report__stat-val mono">{trechos}</span>
              <span className="report__stat-cap">Trechos críticos</span>
            </span>
          )}
        </div>
      </header>

      <div className="report__sections">
        <S1Identificacao index={1} data={report.identificacao} />
        <S2Mapa index={2} />
        <S3ResumoExecutivo index={3} perguntas={report.resumoExecutivo} />
        <S4Ocorrencias index={4} data={report.ocorrencias} />
        <S5Temporal index={5} resumo={report.temporalResumo} />
        <S6DinamicaCriminal index={6} block={report.dinamicaCriminal} />
        <S7EfetivoFM index={7} rows={report.efetivoFM} />
        <S8Fatores index={8} data={report.fatores} />
        <S9Cameras index={9} data={report.cameras} />
        <S10Coincidencias index={10} fallbackMatch={report.coincidencias} planoAcao={report.planoAcao} />
      </div>
    </div>
  )
}
