import { describe, expect, it } from 'vitest'
import {
  contarTarefasTaskConsole,
  criarQueryFiltrosTaskConsole,
  criarRegistroEnvioTaskConsole,
  filtrarHistoricoEnvios,
  filtrarTarefasTaskConsole,
  possuiFiltroAtivo,
} from './filtrosTaskConsole'

const tarefas = [
  { titulo: 'Tarefa A', status: 'Pendente', prioridade: 'Alta', bucket: 'Backlog', responsavelEmail: 'ana@empresa.com' },
  { titulo: 'Tarefa B', status: 'Criada', prioridade: 'Media', bucket: 'Desenvolvimento', responsavelEmail: 'bruno@empresa.com', plannerCorrelationId: 'corr-task-1' },
]

const envios = [
  criarRegistroEnvioTaskConsole({ enviado: true, total: 3, correlationId: 'corr-env-1', mensagem: 'ok' }),
  criarRegistroEnvioTaskConsole({ enviado: false, total: 0, correlationId: 'corr-env-2', mensagem: 'falha', erro: 'flow offline' }),
]

describe('filtrosTaskConsole', () => {
  it('filtra tarefas por status e bucket', () => {
    const resultado = filtrarTarefasTaskConsole(tarefas, { status: 'pendente', bucket: 'Backlog' })
    expect(resultado).toHaveLength(1)
    expect(resultado[0].titulo).toBe('Tarefa A')
  })

  it('filtra historico de envios por status e correlation_id', () => {
    const resultado = filtrarHistoricoEnvios(envios, { envio_status: 'erro', correlation_id: 'corr-env-2' })
    expect(resultado).toHaveLength(1)
    expect(resultado[0].erro).toContain('flow offline')
  })

  it('identifica filtros ativos e conta tarefas', () => {
    expect(possuiFiltroAtivo({ prioridade: 'alta' })).toBe(true)
    expect(criarQueryFiltrosTaskConsole({ status: 'criada', prioridade: 'invalida' })).toEqual({ status: 'criada' })
    expect(contarTarefasTaskConsole(tarefas)).toEqual({ pendentes: 1, criadas: 1, falhas: 0 })
  })
})
