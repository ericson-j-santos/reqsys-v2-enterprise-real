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

  it('detecta DEV pelo locator/runtime PC24x7 e mantém os demais ambientes explícitos', () => {
    expect(detectarAmbientePorHostname('abc.trycloudflare.com')).toBe('desenvolvimento')
    expect(detectarAmbientePorHostname('ericson-j-santos.github.io')).toBe('desenvolvimento')
    expect(detectarAmbientePorHostname('reqsys-app-stg.fly.dev')).toBe('homologacao')
    expect(detectarAmbientePorHostname('reqsys-app.fly.dev')).toBe('producao')
    expect(detectarAmbientePorHostname('127.0.0.1')).toBe('local')
  })

  it('resolve ambiente atual priorizando hostname', () => {
    expect(
      resolverAmbienteAtual({
        environmentHint: 'producao',
        hostname: 'abc.trycloudflare.com',
      }),
    ).toBe('desenvolvimento')
  })

  it('lista local apenas quando hostname é local', () => {
    const remoto = ambientesNavegaveis({ hostname: 'abc.trycloudflare.com' })
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

  it('navega para DEV somente pelo locator assinado e preserva a rota como target relativo', () => {
    const url = montarUrlAmbiente('desenvolvimento', { path: '/task-console?tab=study', preserveRoute: false })
    expect(url).toBe(
      'https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/?target=%2Ftask-console%3Ftab%3Dstudy',
    )
    expect(url).not.toContain('fly.dev')
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
    vi.stubGlobal('window', {
      location: { assign },
      confirm,
    })

    const resultado = irParaAmbiente('producao', { path: '/governanca', preserveRoute: false })

    expect(resultado).toBe(true)
    expect(assign).toHaveBeenCalledWith('https://reqsys-app.fly.dev/governanca')
    vi.unstubAllGlobals()
  })
})
