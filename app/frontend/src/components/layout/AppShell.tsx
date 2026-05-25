// AppShell — layout geral. TopBar fixa, área central rolável (relatório),
// painel do copiloto recolhível à direita.
import { useEffect, useState } from 'react'
import { useReport } from '../../state/reportContext'
import { onCopilotOpen } from '../copilot/copilotBus'
import { CopilotChat } from '../copilot/CopilotChat'
import { ReportView } from '../report/ReportView'
import { DraftBanner } from './DraftBanner'
import { SectionNav } from './SectionNav'
import { TopBar } from './TopBar'

export function AppShell({ onGoHome, onOpenPredictive }: { onGoHome: () => void; onOpenPredictive: () => void }) {
  const { areaId } = useReport()
  const [copilotOpen, setCopilotOpen] = useState(true)

  // seções podem solicitar a abertura do copiloto
  useEffect(() => onCopilotOpen(() => setCopilotOpen(true)), [])

  return (
    <div className={`shell ${copilotOpen ? 'shell--copilot' : ''}`}>
      {/* Skip link (Tarefa 4.2 / WCAG 2.4.1): pula direto para o relatório. */}
      <a className="skip-link" href="#report-main">
        Pular para o conteúdo
      </a>
      <TopBar
        copilotOpen={copilotOpen}
        onToggleCopilot={() => setCopilotOpen((v) => !v)}
        onGoHome={onGoHome}
        onOpenPredictive={onOpenPredictive}
      />

      <aside className="shell__nav">
        <SectionNav />
      </aside>

      <main className="shell__main" id="report-main" tabIndex={-1}>
        <DraftBanner />
        <div className="shell__scroll">
          <ReportView />
        </div>
      </main>

      {copilotOpen && (
        <div className="shell__copilot">
          <CopilotChat key={areaId} onClose={() => setCopilotOpen(false)} />
        </div>
      )}
    </div>
  )
}
