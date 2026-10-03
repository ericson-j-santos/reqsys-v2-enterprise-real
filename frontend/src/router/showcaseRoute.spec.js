import { describe, expect, it } from 'vitest'
import { routes } from './index'

describe('rota pública do ReqSys Showcase', () => {
  it('mantém /showcase e /demo isolados de autenticação e layout operacional', () => {
    const showcase = routes.find((route) => route.path === '/showcase')

    expect(showcase).toBeDefined()
    expect(showcase.alias).toBe('/demo')
    expect(showcase.meta.public).toBe(true)
    expect(showcase.meta.standalone).toBe(true)
    expect(showcase.meta.recurso).toBeUndefined()
  })
})
