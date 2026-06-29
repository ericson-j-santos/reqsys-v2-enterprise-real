import {
  calcularMetricasGovbi,
  carregarHistoricoGovbi,
  contarConsultasGovbi,
  criarQueryFiltrosGovbi,
  criarRegistroConsultaGovbi,
  exportarEvidenciaGovbi,
  filtrarConsultasGovbi,
  GOVBI_HISTORICO_KEY,
  normalizarFiltrosGovbi,
  possuiFiltroAtivo,
  salvarHistoricoGovbi,
} from './filtrosGovbi'

function criarResultado(id, nome, ok, detalhe = 'OK', categoria = 'local') {
  return { id, nome, ok: Boolean(ok), detalhe: String(detalhe ?? ''), categoria }
}

function assertTest(id, nome, fn, categoria = 'local') {
  try {
    const detalhe = fn()
    return criarResultado(id, nome, true, typeof detalhe === 'string' ? detalhe : 'OK', categoria)
  } catch (error) {
    return criarResultado(id, nome, false, error?.message || 'Falha inesperada', categoria)
  }
}

const consultaExemplo = criarRegistroConsultaGovbi({
  pergunta: 'Total por unidade em 2024',
  statusFluxo: 'CONCLUIDO',
  fonte: 'backend',
  latenciaMs: 420,
  correlationId: 'govbi-func-local-1',
  fallback: false,
})

const consultaDegradada = criarRegistroConsultaGovbi({
  pergunta: 'Consulta degradada',
  statusFluxo: 'MODO_DEGRADADO',
  fonte: 'fallback',
  latenciaMs: 12000,
  correlationId: 'govbi-func-local-2',
  fallback: true,
  erro: 'timeout',
})

export function executarTestesLocaisGovbi() {
  const amostras = [consultaExemplo, consultaDegradada]

  return [
    assertTest('filtros-status', 'Normalização de status válido', () => {
      const filtros = normalizarFiltrosGovbi({ status: 'MODO_DEGRADADO' })
      if (filtros.status !== 'MODO_DEGRADADO') throw new Error('Status não normalizado')
      return 'MODO_DEGRADADO'
    }),
    assertTest('filtros-fonte-invalida', 'Rejeição de fonte inválida', () => {
      const filtros = normalizarFiltrosGovbi({ fonte: 'desconhecida' })
      if (filtros.fonte !== '') throw new Error('Fonte inválida deveria ser descartada')
      return 'fonte descartada'
    }),
    assertTest('filtros-query', 'Geração de query string analítica', () => {
      const query = criarQueryFiltrosGovbi({ status: 'ERRO', busca: 'timeout', fonte: 'invalida' })
      if (query.status !== 'ERRO' || query.busca !== 'timeout' || query.fonte) {
        throw new Error('Query gerada fora do contrato')
      }
      return `${Object.keys(query).length} parâmetros`
    }),
    assertTest('filtros-ativos', 'Detecção de filtros ativos', () => {
      if (!possuiFiltroAtivo({ correlation_id: 'abc' })) throw new Error('Filtro ativo não detectado')
      if (possuiFiltroAtivo({})) throw new Error('Filtro vazio deveria ser inativo')
      return 'detecção OK'
    }),
    assertTest('filtros-aplicacao', 'Filtragem analítica combinada', () => {
      const resultado = filtrarConsultasGovbi(amostras, {
        status: 'MODO_DEGRADADO',
        fallback: 'true',
        busca: 'degradada',
      })
      if (resultado.length !== 1 || resultado[0].correlationId !== 'govbi-func-local-2') {
        throw new Error('Filtragem combinada incorreta')
      }
      return '1 consulta filtrada'
    }),
    assertTest('metricas-agregadas', 'Métricas agregadas do histórico', () => {
      const metricas = calcularMetricasGovbi(amostras)
      if (metricas.total !== 2 || metricas.sucesso !== 1 || metricas.erros !== 1) {
        throw new Error('Métricas fora do esperado')
      }
      return `${metricas.latenciaMediaMs} ms médio`
    }),
    assertTest('contagem-consultas', 'Contagem por resultado operacional', () => {
      const contagem = contarConsultasGovbi(amostras)
      if (contagem.fallback !== 1 || contagem.sucesso !== 1) throw new Error('Contagem incorreta')
      return 'sucesso/degradado OK'
    }),
    assertTest('exportacao-evidencia', 'Exportação JSON de evidência', () => {
      const payload = JSON.parse(exportarEvidenciaGovbi(amostras, { status: 'CONCLUIDO' }))
      if (payload.modulo !== 'govbi-ia' || payload.consultas.length !== 1) {
        throw new Error('Payload de evidência inválido')
      }
      return 'JSON válido'
    }),
    assertTest('historico-storage', 'Persistência local do histórico', () => {
      const storage = {
        store: {},
        getItem(key) { return this.store[key] ?? null },
        setItem(key, value) { this.store[key] = value },
      }
      salvarHistoricoGovbi(amostras, storage)
      const carregado = carregarHistoricoGovbi(storage)
      if (carregado.length !== 2 || carregado[0].correlationId !== 'govbi-func-local-1') {
        throw new Error('Roundtrip do histórico falhou')
      }
      if (!storage.store[GOVBI_HISTORICO_KEY]) throw new Error('Chave de histórico ausente')
      return 'roundtrip OK'
    }),
    assertTest('registro-consulta', 'Registro canônico de consulta', () => {
      const registro = criarRegistroConsultaGovbi({
        pergunta: '  teste  ',
        statusFluxo: 'CONCLUIDO',
        fonte: 'backend',
        latenciaMs: 10,
        correlationId: 'corr-test',
      })
      if (registro.pergunta !== 'teste' || !registro.consultadoEm) {
        throw new Error('Registro fora do contrato')
      }
      return registro.id
    }),
  ]
}

export async function executarTestesApiGovbi(client) {
  const resultados = []

  try {
    const { data } = await client.get('/api/govbi/health')
    const payload = data?.data ?? data
    const ok = payload?.service === 'govbi-proxy' && payload?.status === 'ok'
    resultados.push(criarResultado(
      'api-health',
      'Health do proxy GovBI',
      ok,
      ok ? `timeout=${payload.timeout_seconds}s` : 'Resposta fora do contrato',
      'api',
    ))
  } catch (error) {
    resultados.push(criarResultado(
      'api-health',
      'Health do proxy GovBI',
      false,
      error?.message || 'Falha de rede',
      'api',
    ))
  }

  try {
    const { data } = await client.get('/api/govbi/funcionamento')
    const payload = data?.data ?? data
    const ok = Boolean(payload?.completo) && Number(payload?.percentual) === 100
    resultados.push(criarResultado(
      'api-funcionamento',
      'Auto-teste backend GovBI',
      ok,
      ok ? `${payload.aprovados}/${payload.total} (100%)` : `${payload?.aprovados ?? 0}/${payload?.total ?? 0}`,
      'api',
    ))
  } catch (error) {
    resultados.push(criarResultado(
      'api-funcionamento',
      'Auto-teste backend GovBI',
      false,
      error?.message || 'Endpoint indisponível',
      'api',
    ))
  }

  try {
    await client.post('/api/govbi/perguntas', { pergunta: 'oi' })
    resultados.push(criarResultado(
      'api-validacao',
      'Validação de payload mínimo',
      false,
      'Esperava HTTP 422',
      'api',
    ))
  } catch (error) {
    const ok = error?.response?.status === 422
    resultados.push(criarResultado(
      'api-validacao',
      'Validação de payload mínimo',
      ok,
      ok ? 'HTTP 422' : error?.message || 'Falha inesperada',
      'api',
    ))
  }

  try {
    const correlationId = `govbi-func-${Date.now()}`
    const { data } = await client.post(
      '/api/govbi/perguntas',
      {
        pergunta: 'Teste automatizado de funcionamento GovBI',
        formatoResposta: 'tabela',
        exibirSql: true,
      },
      { headers: { 'X-Correlation-Id': correlationId } },
    )
    const camposObrigatorios = ['statusFluxo', 'correlationId', 'resultado', 'explicacao', 'mascaramentoAplicado']
    const faltando = camposObrigatorios.filter((campo) => !(campo in data))
    const ok = faltando.length === 0
    resultados.push(criarResultado(
      'api-contrato-perguntas',
      'Contrato POST /perguntas',
      ok,
      ok ? data.statusFluxo : `Campos ausentes: ${faltando.join(', ')}`,
      'api',
    ))
  } catch (error) {
    resultados.push(criarResultado(
      'api-contrato-perguntas',
      'Contrato POST /perguntas',
      false,
      error?.message || 'Falha na consulta',
      'api',
    ))
  }

  return resultados
}

export function consolidarResultadosFuncionamento(resultados = []) {
  const total = resultados.length
  const aprovados = resultados.filter((item) => item.ok).length
  const reprovados = total - aprovados
  const percentual = total ? Math.round((aprovados / total) * 100) : 0

  return {
    executadoEm: new Date().toISOString(),
    total,
    aprovados,
    reprovados,
    percentual,
    completo: total > 0 && reprovados === 0,
    resultados,
  }
}

export async function executarFuncionamentoGovbi(client) {
  const locais = executarTestesLocaisGovbi()
  const api = await executarTestesApiGovbi(client)
  return consolidarResultadosFuncionamento([...locais, ...api])
}
