import { api } from './api'

const ESTADOS_ATUAIS = new Set(['nao_medido', 'critico', 'atencao', 'adequado', 'avancado'])
const ESTADOS_ALVO = new Set(['adequado', 'avancado', 'excelencia'])
const TENDENCIAS = new Set(['subindo', 'estavel', 'caindo', 'indefinida'])
const CONFIABILIDADES = new Set(['alta', 'media', 'baixa'])
const AMBIENTES_RUNTIME = new Set(['dev', 'stg', 'prod'])
const CAMINHOS_VERSIONADOS = ['backend/', 'frontend/', 'docs/', 'config/', 'scripts/', 'tests/', '.github/']
const REPOSITORIO_URL = (import.meta.env.VITE_GITHUB_REPOSITORY_URL || 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real').replace(/\/$/, '')

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
    evidencias: ['endpoint serviço /v1/estatisticas'],
    pendencias: ['serviço indisponível no momento da carga'],
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
    evidencias: ['marcadores BDD avaliados no serviço'],
    pendencias: ['serviço indisponível no momento da carga'],
  },
  {
    id: 'guard-rails-producao',
    nome: 'Guard rails de produção',
    descricao: 'Validação de verificações obrigatórias produtivos versionados.',
    categoria: 'Segurança',
    valorAtual: 0,
    unidade: '%',
    tendencia: 'indefinida',
    estadoAtual: 'nao_medido',
    estadoAlvo: 'avancado',
    formula: 'verificações obrigatórias versionados e testes de production verificações obrigatórias presentes',
    fonte: {
      id: 'reqsys-security-gates',
      tipo: 'interna',
      nome: 'Production Security Verificações obrigatórias',
      origem: 'backend:settings.validate_production_gates',
      coletadoEm: new Date().toISOString(),
      confiabilidade: 'alta',
      versaoConector: 'backend-v2',
    },
    evidencias: ['Settings.validate_production_gates'],
    pendencias: ['serviço indisponível no momento da carga'],
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
    pendencias: ['serviço indisponível no momento da carga'],
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

export function validarArtifactRuntime(artifact) {
  const motivos = []
  const origem = artifact?.evidence_source || artifact?.source
  const ambiente = String(artifact?.environment || artifact?.ambiente || '').toLowerCase()
  const runId = artifact?.source_run_id || artifact?.run_id
  const headSha = artifact?.source_head_sha || artifact?.head_sha || artifact?.merge_sha
  const observadoEm = artifact?.observed_at || artifact?.observado_em || artifact?.generated_at
  const atestacaoVerificada = artifact?.verified === true
    || artifact?.attestation_verified === true
    || artifact?.verification_status === 'verified'

  if (!artifact || typeof artifact !== 'object') motivos.push('Artefato execução ausente.')
  if (origem !== 'runtime') motivos.push('Origem do artefato não é execução.')
  if (!AMBIENTES_RUNTIME.has(ambiente)) motivos.push('Ambiente execução inválido ou ausente.')
  if (!String(runId || '').trim()) motivos.push('Run ID verificável ausente.')
  if (!/^[a-f0-9]{40}$/i.test(String(headSha || ''))) motivos.push('SHA execução completo e verificável ausente.')
  if (!observadoEm || Number.isNaN(new Date(observadoEm).getTime())) motivos.push('Timestamp execução válido ausente.')
  if (!atestacaoVerificada) motivos.push('Atestação execução positiva e verificável ausente.')

  return {
    valido: motivos.length === 0,
    motivos,
    ambiente: ambiente || null,
    runId: runId ? String(runId) : null,
    headSha: headSha ? String(headSha) : null,
    observadoEm: observadoEm || null,
  }
}

export function resolverRetornoEstatisticas(returnTo) {
  const destino = typeof returnTo === 'string' ? returnTo : ''
  if (!destino.startsWith('/estatisticas') || destino.startsWith('//')) return '/estatisticas'
  return destino
}

export function construirHistoricoIndicador(historicoPayload, indicadorId) {
  const snapshots = Array.isArray(historicoPayload?.snapshots) ? historicoPayload.snapshots : []
  return snapshots
    .map((snapshot) => {
      const indicador = Array.isArray(snapshot?.indicadores)
        ? snapshot.indicadores.find((item) => item.id === indicadorId)
        : null
      if (!indicador) return null
      return {
        coletadoEm: snapshot.coletado_em || indicador.fonte?.coletadoEm || null,
        valor: indicador.valorAtual,
        unidade: indicador.unidade || '',
        estado: indicador.estadoAtual,
        tendencia: indicador.tendencia,
        correlationId: snapshot.correlation_id || null,
        ambiente: snapshot.ambiente || null,
      }
    })
    .filter(Boolean)
    .sort((a, b) => new Date(a.coletadoEm || 0) - new Date(b.coletadoEm || 0))
}

function normalizarValor(valor) {
  if (typeof valor === 'number') return Math.max(0, Math.min(100, valor))
  const convertido = Number(String(valor).replace('%', '').replace(',', '.'))
  return Number.isFinite(convertido) ? Math.max(0, Math.min(100, convertido)) : 0
}

function extrairScoreRuntime(artifact) {
  const candidatos = [artifact?.score, artifact?.maturity_percent, artifact?.confidence_percent, artifact?.score_percent]
  const score = candidatos.find((valor) => Number.isFinite(Number(valor)))
  return score === undefined ? null : Math.round(normalizarValor(Number(score)))
}

function urlExternaSegura(valor) {
  if (!valor) return null
  try {
    const url = new URL(valor)
    return url.protocol === 'https:' ? url.toString() : null
  } catch {
    return null
  }
}

function caminhoVersionado(evidencia) {
  if (typeof evidencia !== 'string') return null
  const candidato = CAMINHOS_VERSIONADOS.find((prefixo) => evidencia.includes(prefixo))
  if (!candidato) return null
  const inicio = evidencia.indexOf(candidato)
  const trecho = evidencia.slice(inicio).split(/[\s,;)]/)[0]
  return trecho.replace(/[.:]+$/, '')
}

function construirLinksEvidencias(evidencias) {
  return (Array.isArray(evidencias) ? evidencias : [])
    .map((descricao) => {
      const path = caminhoVersionado(descricao)
      if (!path) return null
      return {
        tipo: 'evidencia_versionada',
        titulo: descricao,
        url: `${REPOSITORIO_URL}/blob/main/${path}`,
        externo: true,
      }
    })
    .filter(Boolean)
}

function construirLinksOperacionais(indicador, correlationId, artifact) {
  const params = new URLSearchParams()
  if (correlationId) params.set('correlation_id', correlationId)
  if (indicador?.id) params.set('indicador', indicador.id)
  const query = params.toString()
  const artifactUrl = urlExternaSegura(artifact?.artifact_url || artifact?.url)

  return [
    { tipo: 'logs', titulo: 'Logs correlacionados', url: `/auditoria${query ? `?${query}` : ''}`, externo: false },
    { tipo: 'traces', titulo: 'Traces e monitoramento', url: `/monitoramento-operacional${query ? `?${query}` : ''}`, externo: false },
    {
      tipo: 'artifact',
      titulo: artifactUrl ? 'Artefato execução verificado' : 'Artefatos operacionais',
      url: artifactUrl || `/analytics${query ? `?${query}` : ''}`,
      externo: Boolean(artifactUrl),
    },
  ]
}

export async function carregarEstatisticas() {
  try {
    const resposta = await api.get('/v1/estatisticas')
    const payload = resposta.data?.data
    if (Array.isArray(payload?.indicadores)) {
      return {
        modoOffline: false,
        indicadores: payload.indicadores,
        correlationId: payload.correlation_id || resposta.data?.meta?.correlation_id || null,
        coletadoEm: payload.coletado_em || null,
        ambiente: payload.ambiente || null,
        mensagem: '',
      }
    }
  } catch (erro) {
    console.warn('Falha ao carregar /v1/estatisticas; modo offline ativado.', erro)
  }

  return {
    modoOffline: true,
    indicadores: [],
    correlationId: null,
    coletadoEm: null,
    ambiente: null,
    mensagem: 'serviço /v1/estatisticas indisponível. Os indicadores analíticos não serão exibidos até a conexão ser restabelecida.',
  }
}

export async function carregarDetalheIndicador(indicadorId, correlationId = null) {
  const config = correlationId ? { headers: { 'X-Correlation-ID': correlationId } } : undefined
  const [snapshotResult, historicoResult] = await Promise.allSettled([
    api.get('/v1/estatisticas', config),
    api.get('/v1/estatisticas/historico', config),
  ])

  if (snapshotResult.status !== 'fulfilled') {
    return {
      modoOffline: true,
      naoEncontrado: false,
      indicador: null,
      historico: [],
      mensagem: 'Não foi possível carregar o detalhe do indicador.',
    }
  }

  const resposta = snapshotResult.value
  const payload = resposta.data?.data || {}
  const indicador = Array.isArray(payload.indicadores)
    ? payload.indicadores.find((item) => item.id === indicadorId)
    : null

  if (!indicador) {
    return {
      modoOffline: false,
      naoEncontrado: true,
      indicador: null,
      historico: [],
      correlationId: payload.correlation_id || resposta.data?.meta?.correlation_id || correlationId,
      mensagem: `Indicador ${indicadorId} não encontrado.`,
    }
  }

  const correlationIdEfetivo = payload.correlation_id || resposta.data?.meta?.correlation_id || correlationId || null
  const historicoPayload = historicoResult.status === 'fulfilled' ? historicoResult.value.data?.data : null
  const artifact = indicador.runtimeArtifact || payload.runtime_artifacts?.[indicadorId] || payload.runtime_artifact || null
  const validacaoArtifact = validarArtifactRuntime(artifact)
  const scoreEvidenciado = validacaoArtifact.valido ? extrairScoreRuntime(artifact) : null

  return {
    modoOffline: false,
    naoEncontrado: false,
    indicador,
    correlationId: correlationIdEfetivo,
    coletadoEm: payload.coletado_em || indicador.fonte?.coletadoEm || null,
    ambiente: payload.ambiente || null,
    historico: construirHistoricoIndicador(historicoPayload, indicadorId),
    tendenciaCalculada: historicoPayload?.tendencias?.[indicadorId] || indicador.tendencia || 'indefinida',
    guardRails: validarIndicador(indicador),
    linksEvidencias: construirLinksEvidencias(indicador.evidencias),
    linksOperacionais: construirLinksOperacionais(indicador, correlationIdEfetivo, artifact),
    runtimeArtifact: artifact,
    runtimeArtifactValido: validacaoArtifact.valido,
    runtimeArtifactMotivos: validacaoArtifact.motivos,
    scoreEvidenciado,
    scoreStatus: scoreEvidenciado !== null
      ? 'evidenciado_por_artifact_runtime'
      : (validacaoArtifact.valido ? 'artifact_runtime_sem_score' : 'pendente_artifact_runtime_valido'),
    mensagem: historicoResult.status === 'fulfilled' ? '' : 'Histórico indisponível; estado atual preservado.',
  }
}
