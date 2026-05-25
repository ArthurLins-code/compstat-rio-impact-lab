// Contrato compartilhado — espelho de app/backend/report/models.py.
// O backend é a fonte de verdade; manter em sincronia manual.

export type Confianca = 'alta' | 'media' | 'baixa';
export type TipoFonte = 'quantitativo' | 'relint' | 'disque' | 'fator' | 'camera' | 'dominio' | 'cpsr';
export type CamadaMatch = 'mancha' | 'fator' | 'dinamica' | 'lacuna_camera';
export type StatusBloco = 'gerado' | 'nao_gerado' | 'erro' | 'dados_indisponiveis';

export interface SourceCitation {
  kind: TipoFonte;
  label: string;              // rótulo de negócio
  quote?: string;             // trecho LITERAL (relint/disque)
  fullText?: string;          // texto completo p/ popover
  recordCount?: number;       // quando quantitativo
  docId?: string;
  location?: { lat: number; lon: number };
  confidence?: Confianca;
}

export interface Provenance {
  rationale: string;          // "por que/como" em linguagem de gestor
  confidence: Confianca;
  sources: SourceCitation[];
  warnings?: string[];
  technicalDetail?: string;   // drill-down opcional
}

export interface AiBlock {
  blockId: string;
  sectionId: string;
  status: StatusBloco;
  text: string;
  editedByHuman?: boolean;
  provenance?: Provenance;
  geradoEm?: string;
}

// ---- Match ("bingo") ----
export interface FatorProximo { category: string; orgao?: string; dist_m: number; }
export interface Cobertura { camerasRaio: number; lacuna: boolean; }
export interface Coincidencia {
  id: string;
  lat: number; lon: number;
  score: number;
  camadas: CamadaMatch[];
  nOcorrencias: number;
  fatores: FatorProximo[];
  cobertura: Cobertura;
  faccao?: string;
  justificativa: string;
  provenance: Provenance;
}
export interface MatchResult {
  areaId: number;
  scoreArea: number;
  camadasArea: string[];
  coincidencias: Coincidencia[];
  resumo: string;
}

// ---- Seções determinísticas ----
export interface Periodo { de: string; ate: string; }
export interface Identificacao {
  areaFM: number; nomeArea: string; bairros: string[];
  aisp: string; dp: string; bpm: string; baseFM: string; subprefeitura: string;
  influenciaGrupoCriminoso: string[]; trechosCriticos?: number;
  provenance: Provenance;
}
export interface IndicadoresPeriodo {
  roubos: number; furtos?: number; total: number; rankingEntreAreas: number; variacaoPct?: number;
}
export interface DistribuicaoTipo { tipo: string; qtd: number; rank: number; }
export interface Ocorrencias { indicadores: IndicadoresPeriodo; distribuicao: DistribuicaoTipo[]; provenance: Provenance; }
export interface FatorOrgao { fator: string; descricao: string; orgaoResponsavel?: string; qtd: number; provenance?: Provenance; }
export interface FatoresIncidencia { rows: FatorOrgao[]; provenance: Provenance; }
export interface Cameras { total: number; provenance: Provenance; }
export interface PerguntaNorteadora { id: string; pergunta: string; diagnostico: AiBlock; operacao: string; observacoes: string; }
export interface EfetivoRow { blockId: string; campo: string; situacaoAtual: string; sugestao: string; justificativa: string; provenance?: Provenance; }
export interface AcaoRow { id: string; acao: string; responsavel?: string; prazo: string; status: string; provenance?: Provenance; }
export interface TemporalMatrix {
  matrix: number[][]; dias: string[];
  periodoPredominante: string; diaCritico: string; horaCritica?: number;
  coverage: Record<string, number>;
}
export interface AreaInfo { areaId: number; nomeArea: string; totalOcorrencias: number; scoreArea?: number; }

// Resumo de área para a página inicial (cards por urgência). Espelha M.AreaResumo.
export interface AreaResumo {
  areaId: number;
  nomeArea: string;
  ranking: number;            // 1 = mais urgente (ranking_ocorrencias)
  totalOcorrencias: number;
  nDisque: number;
  nCameras: number;
  nPsrCpsr: number;
  picoDiaSemana: string;
  picoHora: number | null;
  principalFator: string | null;
}

export interface Relatorio {
  areaId: number; nomeArea: string; periodo: Periodo; rascunho: boolean;
  identificacao: Identificacao;
  resumoExecutivo: PerguntaNorteadora[];
  ocorrencias: Ocorrencias;
  temporalResumo: AiBlock;
  dinamicaCriminal: AiBlock;
  efetivoFM: EfetivoRow[];
  fatores: FatoresIncidencia;
  cameras: Cameras;
  coincidencias: MatchResult;
  planoAcao: AcaoRow[];
}

// ---- Eventos SSE do copiloto ----
export type CopilotEvent =
  | { type: 'tool_call'; tool: string; friendlyLabel: string }
  | { type: 'tool_result'; tool: string; friendlyLabel: string; recordCount?: number }
  | { type: 'text'; delta: string }
  | { type: 'provenance'; provenance: Provenance }
  | { type: 'suggestion'; sectionId: string; blockId: string; currentText: string; proposedText: string; provenance: Provenance }
  | { type: 'error'; message: string }
  | { type: 'done' };

// ---- Health/frescor (Fase 5 / Tarefa 5.2) ----
export type StatusFrescor = 'verde' | 'ambar' | 'vermelho'

export interface DatasetFrescor {
  nome: string
  idadeHoras: number | null
  slaHoras: number
  status: StatusFrescor
  presente: boolean
}

export interface HealthData {
  datasets: DatasetFrescor[]
  statusGeral: StatusFrescor
  computadoEm: string
}

// Áreas FM (id -> nome curto), para o seletor
export const AREAS_FM: Record<number, string> = {
  2: 'Rodoviária / Terminal Gentileza',
  9: 'Metrô Botafogo / São Clemente',
  10: 'Jardim de Alah',
  11: 'Campo Grande / Calçadão',
  12: 'Rio Sul',
  14: 'Praia de Botafogo / Marquês de Abrantes',
  19: 'São Francisco Xavier / Afonso Pena',
  20: 'Presidente Vargas / Central',
};
