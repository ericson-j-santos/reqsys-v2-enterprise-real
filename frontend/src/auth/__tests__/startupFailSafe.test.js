import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const here = dirname(fileURLToPath(import.meta.url))
const mainSource = readFileSync(resolve(here, '../../main.js'), 'utf8')
const indexSource = readFileSync(resolve(here, '../../../index.html'), 'utf8')

describe('startup fail-safe', () => {
  it('monta a interface antes do bootstrap MSAL fora do retorno OAuth', () => {
    const mountAt = mainSource.indexOf("app.mount('#app')")
    const authAt = mainSource.indexOf('void inicializarAutenticacao(caminhoInicial)')

    expect(mountAt).toBeGreaterThan(-1)
    expect(authAt).toBeGreaterThan(-1)
    expect(mountAt).toBeLessThan(authAt)
  })

  it('consome o retorno OAuth antes de montar o router e preservar code/state', () => {
    const oauthAt = mainSource.indexOf('if (retornoMicrosoft) {')
    const awaitedAuthAt = mainSource.indexOf('await inicializarAutenticacao(caminhoInicial, true)')
    const mountAt = mainSource.indexOf("app.mount('#app')")

    expect(oauthAt).toBeGreaterThan(-1)
    expect(awaitedAuthAt).toBeGreaterThan(oauthAt)
    expect(awaitedAuthAt).toBeLessThan(mountAt)
  })

  it('mantem falha do callback visivel e registra codigo diagnostico sem token', () => {
    expect(mainSource).toContain("localStorage.setItem('azure_login_error', msg)")
    expect(mainSource).toContain('MSAL_CALLBACK_WITHOUT_ID_TOKEN')
    expect(mainSource).toContain("localStorage.removeItem('azure_login_error')")
  })

  it('nao bloqueia o mount aguardando MSAL diretamente', () => {
    const mountAt = mainSource.indexOf("app.mount('#app')")
    const redirectAt = mainSource.indexOf('await handleRedirectResult()')
    const silentAt = mainSource.indexOf('await acquireIdTokenSilent()')

    expect(mountAt).toBeGreaterThan(-1)
    expect(redirectAt).toBeGreaterThan(-1)
    expect(silentAt).toBeGreaterThan(-1)
    expect(mountAt).toBeLessThan(mainSource.indexOf('void inicializarAutenticacao(caminhoInicial)'))
  })

  it('nao bloqueia o mount aguardando a rota inicial', () => {
    const mountAt = mainSource.indexOf("app.mount('#app')")

    expect(mountAt).toBeGreaterThan(-1)
    expect(mainSource).not.toContain('await router.isReady()')
  })

  it('mantem fallback visivel se o bundle nao montar', () => {
    expect(indexSource).toContain('Carregando ReqSys…')
    expect(indexSource).toContain('o runtime local não conseguiu iniciar a interface')
  })
})
