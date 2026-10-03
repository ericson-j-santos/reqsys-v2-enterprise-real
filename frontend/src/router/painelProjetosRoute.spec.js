import { describe, expect, it } from 'vitest'
import { routes } from './index'

describe('rota do Painel de projetos', () => {
  it('expõe o painel consolidado sem quebrar a rota legada de integrações', () => {
    const painel = routes.find((route) => route.path === '/painel-integracao')

    expect(painel).toBeDefined()
    expect(painel.alias).toBe('/painel-projetos')
    expect(painel.meta.recurso).toBe('dashboard:read')
  })
})
