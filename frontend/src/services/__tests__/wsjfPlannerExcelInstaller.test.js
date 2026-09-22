import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { acquireFlowManagementToken } from '../../auth/msal'
import {
  carregarContratoWsjf,
  diagnosticarWorkbookWsjf,
  instalarWsjfPlannerExcel,
  regenerarWorkbookWsjf,
  somenteAmbientesDev,
  somenteArquivoWsjf,
  validarWsjfPlannerExcel,
} from '../wsjfPlannerExcelInstaller'

vi.mock('../api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

vi.mock('../../auth/msal', () => ({
  acquireFlowManagementToken: vi.fn(),
}))

vi.mock('../copilotMemoryInstaller', () => ({
  carregarStatusInstalacao: vi.fn(),
  listarArquivosInstalacao: vi.fn(),
  listarConexoesInstalacao: vi.fn(),
  listarGruposInstalacao: vi.fn(),
  listarPlanosInstalacao: vi.fn(),
  mensagemErroInstalacao: vi.fn((error) => error?.message || 'erro'),
}))

describe('wsjfPlannerExcelInstaller', () => {
  beforeEach(() => vi.clearAllMocks())

  it('mantem somente o arquivo WSJF.xlsx', () => {
    const arquivos = somenteArquivoWsjf([
      { nome: 'CopilotMemory.xlsx' },
      { nome: 'WSJF.xlsx' },
      { nome: 'wsjf.XLSX' },
    ])

    expect(arquivos).toHaveLength(2)
    expect(arquivos.every((item) => item.nome.toLowerCase() === 'wsjf.xlsx')).toBe(true)
  })

  it('mantem somente ambientes identificados como desenvolvimento', () => {
    const ambientes = somenteAmbientesDev([
      { nome: 'ReqSys DEV', id: 'a' },
      { nome: 'ReqSys STG', id: 'b' },
      { nome: 'Production', id: 'c' },
      { nome: 'Desenvolvimento Power Platform', id: 'd' },
    ])

    expect(ambientes.map((item) => item.id)).toEqual(['a', 'd'])
  })

  it('carrega o contrato WSJF', async () => {
    api.get.mockResolvedValueOnce({ data: { data: { profile: 'wsjf_planner_excel_simples' } } })

    const resultado = await carregarContratoWsjf()

    expect(api.get).toHaveBeenCalledWith('/v1/hub-lowcode/wsjf/planner-excel/contract')
    expect(resultado.profile).toBe('wsjf_planner_excel_simples')
  })

  it('valida sem permitir confirmacao acidental', async () => {
    api.post.mockResolvedValueOnce({ data: { data: { profile: 'wsjf_planner_excel_simples' } } })

    await validarWsjfPlannerExcel({ environment_id: 'dev', confirmar: true })

    expect(api.post).toHaveBeenCalledWith(
      '/v1/hub-lowcode/wsjf/planner-excel/validate',
      { environment_id: 'dev', confirmar: false },
    )
  })

  it('instala apenas quando a chamada explicita usa confirmar true, com token delegado do Power Automate', async () => {
    acquireFlowManagementToken.mockResolvedValue('flow-token-123')
    api.post.mockResolvedValueOnce({ data: { data: { dispatched: true } } })

    await instalarWsjfPlannerExcel({ environment_id: 'dev', confirmar: false })

    expect(api.post).toHaveBeenCalledWith(
      '/v1/hub-lowcode/wsjf/planner-excel/deploy',
      { environment_id: 'dev', confirmar: true },
      { headers: { 'X-Power-Automate-Token': 'flow-token-123' } },
    )
  })

  it('diagnostica a planilha do tenant enviando apenas drive e arquivo', async () => {
    api.post.mockResolvedValueOnce({ data: { data: { compativel: false, precisa_reparo: true } } })

    const resultado = await diagnosticarWorkbookWsjf({
      excel_drive: 'drive-1',
      excel_file: 'item-1',
      excel_source: 'groups/g',
    })

    expect(api.post).toHaveBeenCalledWith(
      '/v1/hub-lowcode/wsjf/planner-excel/excel/diagnostico',
      { excel_drive: 'drive-1', excel_file: 'item-1' },
    )
    expect(resultado.precisa_reparo).toBe(true)
  })

  it('regenera a planilha somente com confirmacao explicita', async () => {
    api.post.mockResolvedValueOnce({ data: { data: { reparado: true } } })

    const resultado = await regenerarWorkbookWsjf({ excel_drive: 'drive-1', excel_file: 'item-1' })

    expect(api.post).toHaveBeenCalledWith(
      '/v1/hub-lowcode/wsjf/planner-excel/excel/reparar',
      { excel_drive: 'drive-1', excel_file: 'item-1', confirmar: true },
    )
    expect(resultado.reparado).toBe(true)
  })

  it('instala sem o header quando nao ha token (backend responde com mensagem clara)', async () => {
    acquireFlowManagementToken.mockResolvedValue(null)
    api.post.mockResolvedValueOnce({ data: { data: { dispatched: false } } })

    await instalarWsjfPlannerExcel({ environment_id: 'dev', confirmar: false })

    expect(api.post).toHaveBeenCalledWith(
      '/v1/hub-lowcode/wsjf/planner-excel/deploy',
      { environment_id: 'dev', confirmar: true },
      { headers: {} },
    )
  })
})
