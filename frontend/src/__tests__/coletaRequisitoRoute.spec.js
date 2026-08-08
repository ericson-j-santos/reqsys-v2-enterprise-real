import { describe, expect, it } from 'vitest'

import { routes } from '../router'


describe('rota de coleta governada de requisitos', () => {
  it('publica a rota nativa com a mesma permissão de escrita de requisitos', () => {
    const rota = routes.find((item) => item.path === '/requisitos/coleta')

    expect(rota).toBeDefined()
    expect(rota.meta?.recurso).toBe('requisitos:write')
    expect(rota.component).toBeTruthy()
  })

  it('mantém a coleta fora das rotas públicas', () => {
    const rota = routes.find((item) => item.path === '/requisitos/coleta')

    expect(rota.meta?.public).not.toBe(true)
  })
})
