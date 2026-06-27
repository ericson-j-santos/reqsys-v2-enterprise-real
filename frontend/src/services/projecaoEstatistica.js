const RISK_SCORES = {
  Baixo: 25,
  'Medio/Baixo': 40,
  Medio: 60
}

export const referenciaTemporal = '27/06/2026 21:00 BRT'

export const estadoAtualConsolidado = [
  { id: 'arquitetura-base', nome: 'Arquitetura base', percentual: 88, maturidade: 'Alta' },
  { id: 'ci-cd-governado', nome: 'CI/CD governado', percentual: 82, maturidade: 'Alta' },
  { id: 'living-architecture', nome: 'Living Architecture', percentual: 74, maturidade: 'Media/Alta' },
  { id: 'observabilidade-analytics', nome: 'Observabilidade/Analytics', percentual: 71, maturidade: 'Media/Alta' },
  { id: 'runtime-operacional', nome: 'Runtime operacional', percentual: 68, maturidade: 'Media' },
  { id: 'ux-operacional', nome: 'UX operacional / dashboards', percentual: 72, maturidade: 'Media/Alta' },
  { id: 'automacao-autonoma', nome: 'Automacao autonoma', percentual: 63, maturidade: 'Media' },
  { id: 'governanca-enterprise', nome: 'Governanca enterprise', percentual: 79, maturidade: 'Alta' },
  { id: 'ambientes-sincronizados', nome: 'Ambientes sincronizados', percentual: 61, maturidade: 'Media' },
  { id: 'padrao-ouro', nome: 'Producao padrao ouro consolidado', percentual: 54, maturidade: 'Media' }
]

export const velocidadeAtualObservada = [
  { id: 'prs-dia', nome: 'PRs/dia uteis', minimo: 8, maximo: 18, unidade: 'PRs/dia' },
  { id: 'merges-dia', nome: 'Merges verdes/dia', minimo: 6, maximo: 14, unidade: 'merges/dia' },
  { id: 'correcoes-ci', nome: 'Correcao de CI por ciclo', minimo: 2, maximo: 7, unidade: 'ajustes/ciclo' },
  { id: 'incrementos-paralelos', nome: 'Incrementos paralelos seguros', minimo: 3, maximo: 5, unidade: 'frentes' },
  { id: 'lead-time', nome: 'Lead time medio PR -> merge', minimo: 18, maximo: 90, unidade: 'min' },
  { id: 'estabilizacao-ci', nome: 'Taxa de estabilizacao de CI', minimo: 83, maximo: 83, unidade: '%' }
]

export const percentualConclusao = [
  { id: 'codigo-implementado', nome: 'Codigo implementado', percentual: 78 },
  { id: 'codigo-validado', nome: 'Codigo validado', percentual: 69 },
  { id: 'evidencia-operacional', nome: 'Evidencia operacional consolidada', percentual: 58 },
  { id: 'governanca-enterprise', nome: 'Governanca enterprise consolidada', percentual: 64 },
  { id: 'ambientes-sincronizados', nome: 'Ambientes realmente sincronizados', percentual: 61 },
  { id: 'runtime-analitico', nome: 'Runtime navegavel/analitico', percentual: 67 },
  { id: 'autonomia-operacional', nome: 'Autonomia operacional', percentual: 55 },
  { id: 'padrao-ouro', nome: 'Padrao ouro total consolidado', percentual: 52 }
]

export const gapsRestantes = [
  { id: 'consolidacao-runtime', nome: 'Consolidacao runtime', gap: 18 },
  { id: 'evidencias-automatizadas', nome: 'Evidencias automatizadas', gap: 22 },
  { id: 'operacao-autonoma', nome: 'Operacao autonoma', gap: 31 },
  { id: 'analytics-drilldown', nome: 'Analytics/drill-down total', gap: 27 },
  { id: 'hardening-producao', nome: 'Hardening producao', gap: 24 },
  { id: 'sincronizacao-ambientes', nome: 'Sincronizacao ambientes', gap: 39 },
  { id: 'governanca-viva', nome: 'Governanca viva completa', gap: 21 },
  { id: 'ux-operacional', nome: 'UX operacional enterprise', gap: 17 }
]

export const cenarioComparativo = [
  {
    id: 'mvp',
    nome: 'MVP robusto',
    conservador: { minimo: 3, maximo: 6, label: 'MVP operacional consolidado' },
    acelerado: { minimo: 2, maximo: 4, label: 'MVP robusto' }
  },
  {
    id: 'ambientes',
    nome: 'Ambientes sincronizados',
    conservador: { minimo: 5, maximo: 9, label: 'Ambientes sincronizados' },
    acelerado: { minimo: 4, maximo: 7, label: 'Ambientes quase totalmente sincronizados' }
  },
  {
    id: 'runtime',
    nome: 'Runtime operacional forte',
    conservador: { minimo: 7, maximo: 12, label: 'Runtime operacional robusto' },
    acelerado: { minimo: 5, maximo: 8, label: 'Producao utilizavel forte' }
  },
  {
    id: 'padrao-ouro-tecnico',
    nome: 'Padrao ouro tecnico',
    conservador: { minimo: 14, maximo: 22, label: 'Padrao ouro tecnico' },
    acelerado: { minimo: 10, maximo: 16, label: 'Padrao ouro tecnico' }
  },
  {
    id: 'consolidacao-enterprise',
    nome: 'Consolidacao enterprise completa',
    conservador: { minimo: 21, maximo: 35, label: 'Padrao ouro consolidado total' },
    acelerado: { minimo: 14, maximo: 24, label: 'Consolidacao enterprise completa' }
  }
]

export const gargalosPrincipais = [
  'Estabilizacao continua de CI',
  'Sincronizacao entre ambientes',
  'Evidencia operacional automatica',
  'Consolidacao runtime-driven',
  'Reducao de acoplamentos residuais',
  'Observabilidade fim-a-fim',
  'Hardening de producao'
]

export const riscosEstatisticos = [
  { id: 'regressao-arquitetural', nome: 'Regressao arquitetural', nivel: 'Baixo' },
  { id: 'colisao-branches', nome: 'Colisao de branches', nivel: 'Medio/Baixo' },
  { id: 'instabilidade-ci', nome: 'Instabilidade CI', nivel: 'Medio' },
  { id: 'drift-ambientes', nome: 'Drift entre ambientes', nivel: 'Medio' },
  { id: 'escalabilidade-operacional', nome: 'Escalabilidade operacional', nivel: 'Medio' },
  { id: 'rastreabilidade', nome: 'Perda de rastreabilidade', nivel: 'Baixo' },
  { id: 'acoplamento-oculto', nome: 'Acoplamento oculto', nivel: 'Medio/Baixo' }
]

export const tendenciasAtuais = [
  { id: 'velocidade', nome: 'Velocidade', valor: 'Alta tracao', tendencia: 'Forte' },
  { id: 'maturidade', nome: 'Maturidade', valor: 'Alta tracao', tendencia: 'Forte' },
  { id: 'governanca', nome: 'Governanca', valor: 'Estavel', tendencia: 'Estavel' },
  { id: 'autonomia', nome: 'Autonomia', valor: 'Ganho incremental', tendencia: 'Moderada' },
  { id: 'observabilidade', nome: 'Observabilidade', valor: 'Alta tracao', tendencia: 'Forte' },
  { id: 'runtime-vivo', nome: 'Runtime vivo', valor: 'Alta tracao', tendencia: 'Forte' },
  { id: 'producao', nome: 'Producao consolidada', valor: 'Ganho incremental', tendencia: 'Moderada' }
]

export const probabilidades = [
  { id: 'mvp-semana', nome: 'MVP forte em menos de 1 semana', percentual: 87 },
  { id: 'producao-enterprise', nome: 'Producao utilizavel enterprise', percentual: 81 },
  { id: 'padrao-ouro-tecnico', nome: 'Padrao ouro tecnico real', percentual: 73 },
  { id: 'consolidacao-enterprise', nome: 'Consolidacao enterprise completa', percentual: 61 }
]

export const aceleradores = [
  'CI auto-healing',
  'Geracao automatica de evidencias',
  'Pipeline de validacao consolidada',
  'Sincronizacao Fly.io/runtime',
  'Monitor operacional centralizado',
  'Contratos/shared packages unicos',
  'Reducao de validacoes manuais'
]

export const leituraExecutiva = 'Arquitetura enterprise funcional em aceleracao continua, com necessidade de consolidacao final, sincronizacao de ambientes, automacao total e hardening enterprise.'

function mediaPercentual(itens, chave = 'percentual') {
  if (!itens.length) return 0
  return Math.round(itens.reduce((total, item) => total + item[chave], 0) / itens.length)
}

function mediaFaixa(item) {
  return Math.round((item.minimo + item.maximo) / 2)
}

export function formatarFaixa(minimo, maximo, unidade = 'dias') {
  if (minimo === maximo) return `${minimo} ${unidade}`
  return `${minimo}-${maximo} ${unidade}`
}

export function calcularResumoProjecao() {
  const prsDia = velocidadeAtualObservada.find((item) => item.id === 'prs-dia')
  const mergesDia = velocidadeAtualObservada.find((item) => item.id === 'merges-dia')
  const leadTime = velocidadeAtualObservada.find((item) => item.id === 'lead-time')
  const estabilizacao = velocidadeAtualObservada.find((item) => item.id === 'estabilizacao-ci')

  return {
    consolidacaoMedia: mediaPercentual(percentualConclusao),
    maturidadeEcossistema: mediaPercentual(estadoAtualConsolidado),
    probabilidadeMedia: mediaPercentual(probabilidades),
    capacidadeSemanalPrs: mediaFaixa(prsDia) * 5,
    capacidadeSemanalMerges: mediaFaixa(mergesDia) * 5,
    leadTimeMedioMinutos: mediaFaixa(leadTime),
    estabilizacaoCi: estabilizacao.maximo,
    principalGargalo: gargalosPrincipais[0]
  }
}

export function listarPrincipaisGaps(limit = 3) {
  return [...gapsRestantes].sort((atual, proximo) => proximo.gap - atual.gap).slice(0, limit)
}

export function listarRiscosPriorizados() {
  return [...riscosEstatisticos].sort((atual, proximo) => {
    return (RISK_SCORES[proximo.nivel] || 0) - (RISK_SCORES[atual.nivel] || 0)
  })
}

export function montarCenariosComparativos() {
  return cenarioComparativo.map((cenario) => {
    const conservadorMedio = Math.round((cenario.conservador.minimo + cenario.conservador.maximo) / 2)
    const aceleradoMedio = Math.round((cenario.acelerado.minimo + cenario.acelerado.maximo) / 2)

    return {
      ...cenario,
      conservadorFaixa: formatarFaixa(cenario.conservador.minimo, cenario.conservador.maximo),
      aceleradoFaixa: formatarFaixa(cenario.acelerado.minimo, cenario.acelerado.maximo),
      ganhoEstimadoDias: Math.max(0, conservadorMedio - aceleradoMedio)
    }
  })
}

export function listarAceleradoresPrioritarios(limit = 4) {
  return aceleradores.slice(0, limit)
}
