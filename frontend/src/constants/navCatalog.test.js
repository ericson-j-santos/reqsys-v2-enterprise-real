import { describe, expect, it } from 'vitest'
import { NAV_ITEMS_FLAT, NAV_TEMAS, itemPorRota, temaIdPorRota, temaPorId } from './navCatalog'

describe('navCatalog', () => {
  it('agrupa rotas em temas de negócio', () => {
    expect(NAV_TEMAS.length).toBeGreaterThanOrEqual(5)
    expect(NAV_TEMAS.every((tema) => tema.id && tema.title && tema.items.length > 0)).toBe(true)
  })

  it('mantém lista plana sem duplicar paths', () => {
    const paths = NAV_ITEMS_FLAT.map((item) => item.to)
    expect(new Set(paths).size).toBe(paths.length)
    expect(paths).toContain('/')
    expect(paths).toContain('/requisitos')
    expect(paths).toContain('/governanca')
  })

  it('resolve tema pela rota atual', () => {
    expect(temaIdPorRota('/')).toBe('operacao')
    expect(temaIdPorRota('/requisitos')).toBe('requisitos')
    expect(temaIdPorRota('/figma-github')).toBe('integracoes')
    expect(temaIdPorRota('/auditoria')).toBe('governanca')
    expect(temaPorId('inteligencia').title).toBe('Inteligência')
    expect(itemPorRota('/analytics')?.title).toBe('Analytics')
  })
})
