import { describe, expect, it } from 'vitest'
import { NAV_ITEMS_FLAT } from '../constants/navCatalog'
import { buscarNavegacao, filtrarNavegacaoPermitida, normalizarBusca } from './globalSearch'

describe('busca global de navegação', () => {
  it('ignora acentos, caixa e espaços excedentes', () => {
    expect(normalizarBusca('  RASTREABILIDADE   ')).toBe('rastreabilidade')
    expect(normalizarBusca('Integrações')).toBe('integracoes')
    expect(buscarNavegacao('  RASTREABILIDADE  ')[0].to).toBe('/rastreabilidade')
  })

  it('encontra funcionalidades pela descrição e por múltiplos termos', () => {
    const resultados = buscarNavegacao('planner teams')
    expect(resultados.some((item) => item.to === '/painel-integracao')).toBe(true)
  })

  it('não duplica destinos repetidos entre os temas de navegação', () => {
    const encontrados = buscarNavegacao('requisitos', NAV_ITEMS_FLAT, 40)
    expect(encontrados.filter((item) => item.to === '/requisitos')).toHaveLength(1)
  })

  it('não retorna resultados para consultas vazias, inexistentes ou limite zero', () => {
    expect(buscarNavegacao('   ')).toEqual([])
    expect(buscarNavegacao('xyz-termo-inexistente')).toEqual([])
    expect(buscarNavegacao('requisitos', NAV_ITEMS_FLAT, 0)).toEqual([])
  })

  it('não expõe rotas sem permissão nem destinos inválidos', () => {
    const resolver = (to) => ({
      name: to === '/sem-rota' ? 'not-found' : undefined,
      matched: to === '/sem-rota' ? [{ path: '/:pathMatch(.*)*' }] : [{ path: to }],
      meta: { recurso: to.startsWith('/admin/') ? 'admin:read' : 'dashboard:read' },
    })
    const itens = [
      { to: '/admin/config', title: 'Configuração secreta', tip: 'Administração' },
      { to: '/painel', title: 'Painel', tip: 'Dados públicos' },
      { to: '/sem-rota', title: 'Inexistente', tip: 'Não indexar' },
    ]
    const permitidos = filtrarNavegacaoPermitida(itens, resolver, (recurso) => recurso === 'dashboard:read')
    expect(permitidos.map((item) => item.to)).toEqual(['/painel'])
    expect(buscarNavegacao('secreta', permitidos)).toEqual([])
    expect(buscarNavegacao('painel', permitidos)).toHaveLength(1)
  })
})
