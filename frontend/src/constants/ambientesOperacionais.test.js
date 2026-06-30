import { describe, expect, it, vi } from 'vitest'
import {
  AMBIENTES_OPERACIONAIS,
  ambientePorId,
  ambienteRequerConfirmacao,
  ambientesNavegaveis,
  detectarAmbientePorHostname,
  irParaAmbiente,
  montarUrlAmbiente,
  normalizarAmbienteId,
  resolverAmbienteAtual,
} from './ambientesOperacionais'

describe('ambientesOperacionais', () => {
  it('normaliza aliases comuns de ambiente', () => {
    expect(normalizarAmbienteId('DEV')).toBe('desenvolvimento')
    expect(normalizarAmbienteId('staging')).toBe('homologacao')
    expect(normalizarAmbienteId('production')).toBe('producao')
  })

  it('detecta ambiente pelo hostname Fly.io', () => {
    expect(detectarAmbientePorHostname('reqsys-app-dev.fly.dev')).toBe('desenvolvimento')
    expect(detectarAmbientePorHostname('reqsys-app-stg.fly.dev')).toBe('homologacao')
    expect(detectarAmbientePorHostname('reqsys-app.fly.dev')).toBe('producao')
    expect(detectarAmbientePorHostname('127.0.0.1')).toBe('local')
  })

  it('resolve ambiente atual priorizando hostname', () => {
    expect(
      resolverAmbienteAtual({
        environmentHint: 'producao',
        hostname: 'reqsys-app-dev.fly.dev',
      }),
    ).toBe('desenvolvimento')
  })

  it('lista local apenas quando hostname é local', () => {
    const remoto = ambientesNavegaveis({ hostname: 'reqsys-app-dev.fly.dev' })
    expect(remoto.some((item) => item.id === 'local')).toBe(false)
    expect(remoto).toHaveLength(3)

    const local = ambientesNavegaveis({ hostname: '127.0.0.1' })
    expect(local.some((item) => item.id === 'local')).toBe(true)
    expect(local).toHaveLength(4)
  })

  it('monta URL preservando rota informada', () => {
    const url = montarUrlAmbiente('homologacao', { path: '/governanca', preserveRoute: false })
    expect(url).toBe('https://reqsys-app-stg.fly.dev/governanca')
  })

  it('expõe catálogo com URLs canônicas', () => {
    expect(ambientePorId('prod')?.frontend).toBe('https://reqsys-app.fly.dev')
    expect(AMBIENTES_OPERACIONAIS).toHaveLength(4)
  })

  it('exige confirmação apenas para produção', () => {
    expect(ambienteRequerConfirmacao('prod')).toBe(true)
    expect(ambienteRequerConfirmacao('desenvolvimento')).toBe(false)
    expect(ambienteRequerConfirmacao('homologacao')).toBe(false)
  })

  it('cancela navegação para produção quando confirmação é recusada', () => {
    const assign = vi.fn()
    const confirm = vi.fn(() => false)
    vi.stubGlobal('window', {
      location: { assign },
      confirm,
    })

    const resultado = irParaAmbiente('producao', { path: '/governanca', preserveRoute: false })

    expect(resultado).toBe(false)
    expect(confirm).toHaveBeenCalledOnce()
    expect(assign).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('navega para produção quando confirmação é aceita', () => {
    const assign = vi.fn()
    const confirm = vi.fn(() => true)
    const interceptar = vi.fn()
    vi.stubGlobal('window', {
      location: { assign },
      confirm,
      __reqsysInterceptarNavegacaoAmbiente: interceptar,
    })

    const resultado = irParaAmbiente('producao', { path: '/governanca', preserveRoute: false })

    expect(resultado).toBe(true)
    expect(interceptar).toHaveBeenCalledWith('https://reqsys-app.fly.dev/governanca')
    expect(assign).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('usa interceptador de navegação quando disponível no browser', () => {
    const assign = vi.fn()
    const interceptar = vi.fn()
    vi.stubGlobal('window', {
      location: { assign },
      __reqsysInterceptarNavegacaoAmbiente: interceptar,
    })

    const resultado = irParaAmbiente('homologacao', { path: '/governanca', preserveRoute: false })

    expect(resultado).toBe(true)
    expect(interceptar).toHaveBeenCalledWith('https://reqsys-app-stg.fly.dev/governanca')
    expect(assign).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})
