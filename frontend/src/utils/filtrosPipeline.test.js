import { describe, expect, it } from 'vitest'
import {
  achatarHistoricoPipeline,
  contarEtapasPipeline,
  criarRegistroExecucaoPipeline,
  filtrarEtapasPipeline,
  normalizarFiltrosPipeline,
} from './filtrosPipeline'

const execucao = criarRegistroExecucaoPipeline({
  correlationId: 'corr-pipe-1',
  solicitante: 'ana@empresa.com',
  modoDemo: false,
  statusGeral: 'CONCLUIDO',
  steps: [
    { key: 'normalizar', label: '1. Normalização', status: 'ok', duration: 120, log: 'ok' },
    { key: 'publicar', label: '5. Publicar', status: 'error', duration: 900, log: 'falha redmine' },
  ],
})

describe('filtrosPipeline', () => {
  it('achata historico e filtra por etapa e status', () => {
    const etapas = achatarHistoricoPipeline([execucao])
    expect(etapas).toHaveLength(2)
    const resultado = filtrarEtapasPipeline(etapas, { etapa: 'publicar', status: 'error' })
    expect(resultado).toHaveLength(1)
    expect(resultado[0].correlationId).toBe('corr-pipe-1')
  })

  it('normaliza aliases de query', () => {
    expect(normalizarFiltrosPipeline({ step: 'validar', correlationId: 'corr', duracaoMin: 500 })).toEqual({
      etapa: 'validar',
      status: '',
      categoria: '',
      correlation_id: 'corr',
      data: '',
      busca: '',
      duracao_min: 500,
    })
  })

  it('conta etapas por status', () => {
    const etapas = achatarHistoricoPipeline([execucao])
    expect(contarEtapasPipeline(etapas)).toEqual({ erros: 1, avisos: 0, ok: 1 })
  })
})
