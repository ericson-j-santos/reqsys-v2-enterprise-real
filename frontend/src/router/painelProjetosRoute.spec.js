import { describe, expect, it } from 'vitest'
import { routes } from './index'

describe('rota do Painel de projetos', () => {
  it('expõe o painel consolidado sem quebrar a rota legada de integrações', () => {
    const painel = routes.find((route) => route.path === '/painel-projetos')
    const integracoes = routes.find((route) => route.path === '/painel-integracao')

    expect(painel).toBeDefined()
    expect(painel.component.__name).toBe('PainelProjetosView')
    expect(painel.meta.recurso).toBe('dashboard:read')
    expect(integracoes.component.__name).toBe('PainelIntegracaoView')
  })
})
