import { beforeEach, describe, expect, it } from 'vitest'
import {
  POST_LOGIN_REDIRECT_KEY,
  consumePostLoginRedirect,
  normalizePostLoginRedirect,
  persistPostLoginRedirect,
} from '../postLoginRedirect'

describe('destino apos login Microsoft', () => {
  beforeEach(() => sessionStorage.clear())

  it('preserva e consome uma unica vez a rota interna solicitada', () => {
    expect(persistPostLoginRedirect('/painel-projetos')).toBe('/painel-projetos')
    expect(consumePostLoginRedirect()).toBe('/painel-projetos')
    expect(sessionStorage.getItem(POST_LOGIN_REDIRECT_KEY)).toBeNull()
    expect(consumePostLoginRedirect()).toBe('/')
  })

  it.each(['https://malicioso.example', '//malicioso.example', '/login?redirect=/painel-projetos', '', null])(
    'recusa destino inseguro ou recursivo: %s',
    (destination) => expect(normalizePostLoginRedirect(destination)).toBe('/'),
  )
})
