import { describe, expect, it } from 'vitest'
import router from '../index'

describe('router — runtime validator', () => {
  it('registra rota operacional protegida por dashboard:read', () => {
    const route = router.getRoutes().find((item) => item.path === '/runtime-validator')

    expect(route).toBeTruthy()
    expect(route.meta.recurso).toBe('dashboard:read')
  })
})
