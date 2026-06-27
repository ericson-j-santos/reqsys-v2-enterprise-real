import { api } from './api'

const ESTADOS_ATUAIS = new Set(['nao_medido', 'critico', 'atencao', 'adequado', 'avancado'])
const ESTADOS_ALVO = new Set(['adequado', 'avancado', 'excelencia'])
const TENDENCIAS = new Set(['subindo', 'estavel', 'caindo', 'indefinida'])
const CONFIABILIDADES = new Set(['alta', 'media', 'baixa'])

export const estatisticasInternasIniciais = [
  {
    id: 'maturidade-evidenciada',
    nome: 'Maturidade evidenciada',
    descricao: 'Maturidade consolidada somente com evidências reais e pendências explícitas.',
    categoria: 'Governança',
    valorAtual: 68,
    unidade: '%',
    tendencia: 'estavel',
    estadoAtual: 'adequado',
    estadoAlvo: 'avancado',
    formula: 'média ponderada dos critérios validados / critérios totais',
    fonte: {
      id: 'reqsys-governanca-local',
      tipo: 'interna',
      nome: 'Governança ReqSys',
      origem: 'frontend-runtime-fallback',
      coletadoEm: new Date().toISOString(),
      confiabilidade: 'media',
      versaoConector: 'fallback-v1'
    },
    evidencias: ['ADR versionada', 'especificação da aba estatísticas', 'guard rails documentados'],
    pendencias: ['API /v1/estatisticas indisponível no momento da carga']
  },
  {
    id: 'requisitos-com-bdd',
    nome: 'Requisitos com BDD',
    descricao: 'Percentual de requisitos com critérios de aceite em formato testável.',
    categoria: 'Requisitos',
    valorAtual: 42,
    unidade: '%',
    tendencia: 'subindo',
    estadoAtual: 'atencao',
    estadoAlvo: 'avancado',
    formula: 'requisitos com BDD / total de requisitos',
    fonte: {
      id: 'reqsys-requisitos-local',
      tipo: 'interna',
      nome: 'Requisitos ReqSys',
      origem: 'frontend-runtime-fallback',
      coletadoEm: new Date().toISOString(),
      confiabilidade: 'media',
      versaoConector: 'fallback-v1'
    },
    evidencias: ['modelo de requisitos rastreáveis'],
    pendencias: ['API /v1/estatisticas indisponível no momento da carga']
  },
  {
    id: 'guard-rails-violados',
    nome: 'Guard rails violados',
    descricao: 'Quantidade de bloqueios ou violações de governança identificadas no ciclo atual.',
    categoria: 'Segurança',
    valorAtual: 0,
    unidade: 'itens',
    tendencia: 'estavel',
    estadoAtual: 'adequado',
    estadoAlvo: 'avancado',
    formula: 'total de violações críticas abertas no período',
    fonte: {
      id: 'reqsys-security-local',
      tipo: 'interna',
      nome: 'Guard Rails ReqSys',
      origem: 'frontend-runtime-fallback',
      coletadoEm: new Date().toISOString(),
      confiabilidade: 'media',
      versaoConector: 'fallback-v1'
    },
    evidencias: ['gates documentados para dados externos e mocks'],
    pendencias: ['API /v1/estatisticas indisponível no momento da carga']
  }
]

export const estatisticasExternasIniciais = [
  {
    id: 'fontes-externas-validas',
    nome: 'Fontes externas válidas',
    descricao: 'Fontes externas cadastradas com origem, data de coleta, confiabilidade e validade.',
    categoria: 'Fontes externas',
    valorAtual: 0,
    unidade: 'fontes',
    tendencia: 'indefinida',
    estadoAtual: 'nao_medido',
    estadoAlvo: 'adequado',
    formula: 'fontes externas dentro do TTL / total de fontes externas cadastradas',
    fonte: {
      id: 'external-sources-registry',
      tipo: 'externa',
      nome: 'Registry de fontes externas',
      origem: 'pendente-conector',
      coletadoEm: new Date().toISOString(),
      ttlMinutos: 1440,
      confiabilidade: 'baixa',
      versaoConector: 'planejado-v2'
    },
    evidencias: ['contrato de fonte externa definido'],
    pendencias: ['implementar registry de fontes externas', 'definir conectores autorizados']
  }
]

export function validarIndicador(indicador) {
  const erros = []
  if (!indicador?.id) erros.push('Indicador sem id.')
  if (!indicador?.nome) erros.push('Indicador sem nome.')
  if (!indicador?.formula) erros.push('Indicador sem fórmula documentada.')
  if (!ESTADOS_ATUAIS.has(indicador?.estadoAtual)) erros.push('Estado atual inválido ou ausente.')
  if (!ESTADOS_ALVO.has(indicador?.estadoAlvo)) erros.push('Estado alvo inválido ou ausente.')
  if (!TENDENCIAS.has(indicador?.tendencia)) erros.push('Tendência inválida ou ausente.')
  if (!indicador?.fonte) erros.push('Indicador sem fonte.')
  if (indicador?.fonte) {
    if (!indicador.fonte.id) erros.push('Fonte sem id.')
    if (!indicador.fonte.tipo) erros.push('Fonte sem tipo.')
    if (!indicador.fonte.nome) erros.push('Fonte sem nome.')
    if (!indicador.fonte.origem) erros.push('Fonte sem origem.')
    if (!indicador.fonte.coletadoEm) erros.push('Fonte sem data de coleta.')
    if (!CONFIABILIDADES.has(indicador.fonte.confiabilidade)) erros.push('Confiabilidade da fonte inválida ou ausente.')
    if (indicador.fonte.tipo === 'externa' && !indicador.fonte.ttlMinutos) erros.push('Fonte externa sem TTL.')
  }
  if (indicador?.estadoAtual === 'avancado' && (!indicador.evidencias || indicador.evidencias.length < 2)) {
    erros.push('Estado avançado exige pelo menos duas evidências.')
  }
  return erros
}

export function calcularResumoEstatisticas(indicadores) {
  const total = indicadores.length
  const criticos = indicadores.filter((item) => item.estadoAtual === 'critico').length
  const atencao = indicadores.filter((item) => item.estadoAtual === 'atencao' || item.estadoAtual === 'nao_medido').length
  const externos = indicadores.filter((item) => item.fonte?.tipo === 'externa').length
  const invalidos = indicadores.filter((item) => validarIndicador(item).length > 0).length
  const maturidadeMedia = total
    ? Math.round(indicadores.reduce((acc, item) => acc + normalizarValor(item.valorAtual), 0) / total)
    : 0

  return { total, criticos, atencao, externos, invalidos, maturidadeMedia }
}

function normalizarValor(valor) {
  if (typeof valor === 'number') return Math.max(0, Math.min(100, valor))
  const convertido = Number(String(valor).replace('%', '').replace(',', '.'))
  return Number.isFinite(convertido) ? Math.max(0, Math.min(100, convertido)) : 0
}

export async function carregarEstatisticas() {
  try {
    const resposta = await api.get('/v1/estatisticas')
    const payload = resposta.data?.data
    if (Array.isArray(payload?.indicadores)) {
      return payload.indicadores
    }
  } catch (erro) {
    console.warn('Falha ao carregar /v1/estatisticas; usando fallback local controlado.', erro)
  }

  return [...estatisticasInternasIniciais, ...estatisticasExternasIniciais]
}

export const projecaoConclusaoFallback = {
  schema_version: '1.0.0',
  referencia_temporal: '2026-06-27T21:00:00-03:00',
  modo: 'governado',
  confianca_percentual: 87,
  cenario_ativo: 'acelerado_recomendado',
  leitura_executiva: {
    fase_atual: 'Arquitetura enterprise funcional em aceleração contínua',
    nao_experimental: true,
    demonstra: ['governança', 'evolução incremental consistente', 'arquitetura viva', 'analytics operacional'],
    falta_principalmente: ['consolidação', 'sincronização', 'automação total', 'hardening enterprise final'],
    limitante_principal: 'Não é implementação — são estabilização CI, sync ambientes e evidências automáticas'
  },
  resumo: {
    media_dimensoes_percentual: 71.1,
    media_conclusao_percentual: 63,
    gap_medio_percentual: 24.9,
    padrao_ouro_consolidado_percentual: 52,
    taxa_estabilizacao_ci_percentual: 83
  },
  estado_atual_consolidado: [
    { dimensao: 'Arquitetura base', status_percentual: 88, maturidade: 'Alta' },
    { dimensao: 'CI/CD governado', status_percentual: 82, maturidade: 'Alta' },
    { dimensao: 'Produção padrão ouro consolidado', status_percentual: 54, maturidade: 'Média' }
  ],
  velocidade_observada: {
    prs_por_dia_uteis: { min: 8, max: 18 },
    merges_verdes_por_dia: { min: 6, max: 14 },
    taxa_estabilizacao_ci_percentual: 83
  },
  percentual_conclusao_real: [
    { indicador: 'Código implementado', percentual: 78, tipo: 'evidenciado' },
    { indicador: 'Padrão ouro total consolidado', percentual: 52, tipo: 'evidenciado' }
  ],
  gaps_restantes: [
    { area: 'Sincronização ambientes', gap_percentual: 39 },
    { area: 'Operação autônoma', gap_percentual: 31 }
  ],
  projecao_tempo: {
    conservador: [{ marco: 'MVP operacional consolidado', estimativa_dias_min: 3, estimativa_dias_max: 6, cenario: 'conservador' }],
    acelerado: [{ marco: 'MVP robusto', estimativa_dias_min: 2, estimativa_dias_max: 4, cenario: 'acelerado' }]
  },
  gargalos_principais: ['estabilização contínua de CI', 'sincronização entre ambientes'],
  indice_risco: [{ tipo: 'Instabilidade CI', nivel: 'Médio' }],
  tendencias: [{ indicador: 'Velocidade', tendencia: '↑ Forte' }],
  probabilidades_finais: [{ resultado: 'MVP forte em menos de 1 semana', probabilidade_percentual: 87 }],
  aceleradores_marginais: ['CI auto-healing', 'geração automática de evidências'],
  evidencias: ['fallback local controlado'],
  pendencias: ['API /v1/estatisticas/projecao-conclusao indisponível no momento da carga']
}

export async function carregarProjecaoConclusao() {
  try {
    const resposta = await api.get('/v1/estatisticas/projecao-conclusao')
    const payload = resposta.data?.data
    if (payload?.schema_version) {
      return payload
    }
  } catch (erro) {
    console.warn('Falha ao carregar /v1/estatisticas/projecao-conclusao; usando fallback local.', erro)
  }
  return { ...projecaoConclusaoFallback, coletado_em: new Date().toISOString() }
}
