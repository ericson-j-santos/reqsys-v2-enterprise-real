import { api } from './api'

const ESTADOS_ATUAIS = new Set(['nao_medido', 'critico', 'atencao', 'adequado', 'avancado'])
const ESTADOS_ALVO = new Set(['adequado', 'avancado', 'excelencia'])
const TENDENCIAS = new Set(['subindo', 'estavel', 'caindo', 'indefinida'])
const CONFIABILIDADES = new Set(['alta', 'media', 'baixa'])

/** Indicadores de exemplo usados apenas em testes de validação de contrato. */
export const indicadoresExemploValidacao = [
  {
    id: 'total-requisitos',
    nome: 'Total de requisitos',
    descricao: 'Quantidade total de requisitos cadastrados.',
    categoria: 'Requisitos',
    valorAtual: 0,
    unidade: 'itens',
    tendencia: 'indefinida',
    estadoAtual: 'nao_medido',
    estadoAlvo: 'avancado',
    formula: 'count(requisitos.id)',
    fonte: {
      id: 'reqsys-db-requisitos',
      tipo: 'interna',
      nome: 'Banco operacional ReqSys',
      origem: 'backend-db:requisitos',
      coletadoEm: new Date().toISOString(),
      confiabilidade: 'alta',
      versaoConector: 'backend-v2',
    },
    evidencias: ['endpoint backend /v1/estatisticas'],
    pendencias: ['API indisponível no momento da carga'],
  },
  {
    id: 'requisitos-com-bdd',
    nome: 'Requisitos com BDD',
    descricao: 'Percentual de requisitos com critérios de aceite em formato testável.',
    categoria: 'Requisitos',
    valorAtual: 0,
    unidade: '%',
    tendencia: 'indefinida',
    estadoAtual: 'nao_medido',
    estadoAlvo: 'avancado',
    formula: 'requisitos com BDD / total de requisitos',
    fonte: {
      id: 'reqsys-db-requisitos-bdd',
      tipo: 'interna',
      nome: 'Banco operacional ReqSys',
      origem: 'backend-db:requisitos.descricao',
      coletadoEm: new Date().toISOString(),
      confiabilidade: 'alta',
      versaoConector: 'backend-v2',
    },
    evidencias: ['marcadores BDD avaliados no backend'],
    pendencias: ['API indisponível no momento da carga'],
  },
  {
    id: 'guard-rails-producao',
    nome: 'Guard rails de produção',
    descricao: 'Validação de gates produtivos versionados.',
    categoria: 'Segurança',
    valorAtual: 0,
    unidade: '%',
    tendencia: 'indefinida',
    estadoAtual: 'nao_medido',
    estadoAlvo: 'avancado',
    formula: 'gates versionados e testes de production gates presentes',
    fonte: {
      id: 'reqsys-security-gates',
      tipo: 'interna',
      nome: 'Production Security Gates',
      origem: 'backend:settings.validate_production_gates',
      coletadoEm: new Date().toISOString(),
      confiabilidade: 'alta',
      versaoConector: 'backend-v2',
    },
    evidencias: ['Settings.validate_production_gates'],
    pendencias: ['API indisponível no momento da carga'],
  },
  {
    id: 'fontes-externas-validas',
    nome: 'Fontes externas válidas',
    descricao: 'Fontes externas autorizadas e dentro do TTL.',
    categoria: 'Fontes externas',
    valorAtual: 0,
    unidade: 'fontes',
    tendencia: 'indefinida',
    estadoAtual: 'nao_medido',
    estadoAlvo: 'adequado',
    formula: 'fontes externas válidas / total cadastradas',
    fonte: {
      id: 'external-sources-registry',
      tipo: 'externa',
      nome: 'Registry de fontes externas',
      origem: 'backend:external_sources_registry',
      coletadoEm: new Date().toISOString(),
      ttlMinutos: 1440,
      confiabilidade: 'media',
      versaoConector: 'registry-v1',
    },
    evidencias: ['contrato de fonte externa definido'],
    pendencias: ['API indisponível no momento da carga'],
  },
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
      return {
        modoOffline: false,
        indicadores: payload.indicadores,
        mensagem: '',
      }
    }
  } catch (erro) {
    console.warn('Falha ao carregar /v1/estatisticas; modo offline ativado.', erro)
  }

  return {
    modoOffline: true,
    indicadores: [],
    mensagem: 'API /v1/estatisticas indisponível. Os indicadores analíticos não serão exibidos até a conexão ser restabelecida.',
  }
}
