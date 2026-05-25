// Entrada do i18n (Tarefa 4.5). Hoje só há PT-BR; trocar para `en-US`/
// `es-ES` no futuro = importar outro dicionário aqui.
//
// `t(chave, vars?)` interpola `{nome}` por `vars.nome`. Chave inexistente
// devolve a própria chave (sinal visual evidente em dev — fácil de caçar).
import { PT_BR, type ChaveI18n } from './pt-BR'

const DICIONARIO: Record<string, string> = PT_BR

export function t(chave: ChaveI18n, vars?: Record<string, string | number>): string {
  const texto = DICIONARIO[chave] ?? chave
  if (!vars) return texto
  return texto.replace(/\{(\w+)\}/g, (_, k) => {
    const v = vars[k]
    return v != null ? String(v) : `{${k}}`
  })
}
