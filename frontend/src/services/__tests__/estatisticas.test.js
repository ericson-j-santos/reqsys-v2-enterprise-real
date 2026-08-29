import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  calcularResumoEstatisticas,
  carregarDetalheIndicador,
  carregarEstatisticas,
  construirHistoricoIndicador,
  indicadoresExemploValidacao,
  resolverRetornoEstatisticas,
  validarArtifactRuntime,
  validarIndicador
} from '../estatisticas'
import { api } from '../api'

vi.mock('../api', () => ({
  api: {
    get: vi.fn()
  }
}))

const indicadorApi = {
  id: 'total-requisitos',
  nome: 'Total de requisitos',
  descricao: 'Total real',
  categoria: 'Requisitos',
  valorAtual: 10,
  unidade: 'itens',
  tendencia: 'estavel',
  estadoAtual: 'adequado',
  estadoAlvo: 'avancado',
  formula: 'count(requisitos.id)',
  fonte: {
    id: 'reqsys-db-requisitos',
    tipo: 'interna',
    nome: 'Banco operacional ReqSys',
    origem: 'backend-db:requisitos',
    coletadoEm: '2026-07-31T12:00:00Z',
    confiabilidade: 'alta',
    versaoConector: 'backend-v2'
  },
  evidencias: ['backend/app/services/estatisticas.py', 'endpoint backend /v1/estatisticas'],
  pendencias: []
}

const artifactRuntimeValido = {
  evidence_source: 'runtime',
  environment: 'stg',
  source_run_id: '30500000000',
  source_head_sha: 'a'.repeat(40),
  observed_at: '2026-07-31T12:05:00Z',
  attestation_verified: true,
  score: 92,
  artifact_url: 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30500000000'
}

describe('estatisticas', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('mantem indicadores de exemplo com contrato valido', () => {
    expect(indicadoresExemploValidacao.length).toBeGreaterThan(0)
    expect(indicadoresExemploValidacao.flatMap((indicador) => validarIndicador(indicador))).toEqual([])
  })

  it('bloqueia indicador sem fonte e formula', () => {
    const erros = validarIndicador({
      id: 'indicador-invalido',
      nome: 'Indicador inválido',
      estadoAtual: 'avancado',
      estadoAlvo: 'avancado',
      tendencia: 'subindo',
      evidencias: ['uma evidencia']
    })

    expect(erros).toContain('Indicador sem fórmula documentada.')
    expect(erros).toContain('Indicador sem fonte.')
    expect(erros).toContain('Estado avançado exige pelo menos duas evidências.')
  })

  it('calcula resumo consolidado sem promover estado alvo como atual', () => {
    const resumo = calcularResumoEstatisticas(indicadoresExemploValidacao)

    expect(resumo.total).toBe(4)
    expect(resumo.externos).toBe(1)
    expect(resumo.invalidos).toBe(0)
    expect(resumo.atencao).toBeGreaterThanOrEqual(1)
  })

  it('valida artifact runtime apenas com origem ambiente run sha timestamp e atestacao verificaveis', () => {
    expect(validarArtifactRuntime(artifactRuntimeValido)).toMatchObject({ valido: true, ambiente: 'stg' })

    const invalido = validarArtifactRuntime({ ...artifactRuntimeValido, evidence_source: 'synthetic', source_head_sha: 'curto' })
    expect(invalido.valido).toBe(false)
    expect(invalido.motivos).toContain('Origem do artefato não é execução.')
    expect(invalido.motivos).toContain('SHA execução completo e verificável ausente.')

    const semAtestacao = { ...artifactRuntimeValido }
    delete semAtestacao.attestation_verified
    const resultadoSemAtestacao = validarArtifactRuntime(semAtestacao)
    expect(resultadoSemAtestacao.valido).toBe(false)
    expect(resultadoSemAtestacao.motivos).toContain('Atestação execução positiva e verificável ausente.')
  })

  it('aceita contrato runtime com verification_status positivo e generated_at', () => {
    const artifact = {
      evidence_source: 'runtime',
      environment: 'prod',
      run_id: '30500000001',
      merge_sha: 'b'.repeat(40),
      generated_at: '2026-07-31T12:06:00Z',
      verification_status: 'verified'
    }

    expect(validarArtifactRuntime(artifact)).toMatchObject({ valido: true, ambiente: 'prod' })
  })

  it('preserva retorno somente dentro da área de estatísticas', () => {
    expect(resolverRetornoEstatisticas('/estatisticas?estado=critico')).toBe('/estatisticas?estado=critico')
    expect(resolverRetornoEstatisticas('//dominio-externo.example')).toBe('/estatisticas')
    expect(resolverRetornoEstatisticas('/auditoria')).toBe('/estatisticas')
  })

  it('constrói histórico cronológico do indicador sem misturar outros indicadores', () => {
    const historico = construirHistoricoIndicador({
      snapshots: [
        { coletado_em: '2026-07-31T12:00:00Z', correlation_id: 'corr-2', indicadores: [{ ...indicadorApi, valorAtual: 10 }] },
        { coletado_em: '2026-07-30T12:00:00Z', correlation_id: 'corr-1', indicadores: [{ ...indicadorApi, valorAtual: 8 }] },
        { coletado_em: '2026-07-29T12:00:00Z', indicadores: [{ ...indicadorApi, id: 'outro-indicador' }] }
      ]
    }, indicadorApi.id)

    expect(historico).toHaveLength(2)
    expect(historico.map((item) => item.valor)).toEqual([8, 10])
    expect(historico.map((item) => item.correlationId)).toEqual(['corr-1', 'corr-2'])
  })

  it('carrega indicadores reais via API quando disponiveis', async () => {
    api.get.mockResolvedValueOnce({ data: { data: { indicadores: [indicadorApi], correlation_id: 'corr-lista' } } })

    const resultado = await carregarEstatisticas()

    expect(api.get).toHaveBeenCalledWith('/v1/estatisticas')
    expect(resultado.modoOffline).toBe(false)
    expect(resultado.indicadores).toEqual([indicadorApi])
    expect(resultado.correlationId).toBe('corr-lista')
  })

  it('carrega detalhe completo e atualiza score somente com artifact runtime válido', async () => {
    api.get
      .mockResolvedValueOnce({
        data: {
          data: {
            correlation_id: 'corr-detalhe',
            coletado_em: '2026-07-31T12:00:00Z',
            ambiente: 'stg',
            indicadores: [indicadorApi],
            runtime_artifacts: { [indicadorApi.id]: artifactRuntimeValido }
          }
        }
      })
      .mockResolvedValueOnce({
        data: {
          data: {
            tendencias: { [indicadorApi.id]: 'subindo' },
            snapshots: [{
              coletado_em: '2026-07-30T12:00:00Z',
              correlation_id: 'corr-historico',
              ambiente: 'dev',
              indicadores: [{ ...indicadorApi, valorAtual: 8 }]
            }]
          }
        }
      })

    const resultado = await carregarDetalheIndicador(indicadorApi.id, 'corr-solicitacao')

    expect(api.get).toHaveBeenNthCalledWith(1, '/v1/estatisticas', { headers: { 'X-Correlation-ID': 'corr-solicitacao' } })
    expect(api.get).toHaveBeenNthCalledWith(2, '/v1/estatisticas/historico', { headers: { 'X-Correlation-ID': 'corr-solicitacao' } })
    expect(resultado.indicador).toEqual(indicadorApi)
    expect(resultado.correlationId).toBe('corr-detalhe')
    expect(resultado.tendenciaCalculada).toBe('subindo')
    expect(resultado.runtimeArtifactValido).toBe(true)
    expect(resultado.scoreEvidenciado).toBe(92)
    expect(resultado.linksEvidencias[0].url).toContain('/blob/main/backend/app/services/estatisticas.py')
    expect(resultado.linksOperacionais.map((item) => item.tipo)).toEqual(['logs', 'traces', 'artifact'])
  })

  it('não atualiza score quando artifact é sintético ou incompleto', async () => {
    api.get
      .mockResolvedValueOnce({
        data: {
          data: {
            indicadores: [indicadorApi],
            runtime_artifacts: {
              [indicadorApi.id]: { ...artifactRuntimeValido, evidence_source: 'synthetic', source_head_sha: 'invalido' }
            }
          }
        }
      })
      .mockResolvedValueOnce({ data: { data: { snapshots: [], tendencias: {} } } })

    const resultado = await carregarDetalheIndicador(indicadorApi.id)

    expect(resultado.runtimeArtifactValido).toBe(false)
    expect(resultado.scoreEvidenciado).toBeNull()
    expect(resultado.scoreStatus).toBe('pendente_artifact_runtime_valido')
  })

  it('ativa modo offline sem KPIs inventados quando API falha', async () => {
    api.get.mockRejectedValueOnce(new Error('api indisponivel'))

    const resultado = await carregarEstatisticas()

    expect(resultado.modoOffline).toBe(true)
    expect(resultado.indicadores).toEqual([])
    expect(resultado.mensagem).toMatch(/indisponível/i)
  })
})
