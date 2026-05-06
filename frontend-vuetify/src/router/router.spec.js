import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'

const Dummy = { template: '<div />' }

let authState = {
  autenticado: false,
  pode: () => false,
}

vi.mock('../stores/auth', () => ({
  useAuthStore: () => authState,
}))

function buildTestRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: Dummy, meta: { public: true } },
      { path: '/', component: Dummy, meta: { permissao: 'dashboard:read' } },
      { path: '/auditoria', component: Dummy, meta: { permissao: 'auditoria:read' } },
      { path: '/relatorios', component: Dummy, meta: { permissao: 'relatorios:read' } },
    ],
  })

  router.beforeEach((to) => {
    const auth = authState
    if (to.meta.public) return true
    if (!auth.autenticado) return '/login'
    if (to.meta.permissao && !auth.pode(to.meta.permissao)) return '/'
    return true
  })

  return router
}

describe('Router guard - rota publica', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState = { autenticado: false, pode: () => false }
  })

  it('permite /login sem autenticacao', async () => {
    const router = buildTestRouter()
    await router.push('/login')
    expect(router.currentRoute.value.path).toBe('/login')
  })
})

describe('Router guard - nao autenticado', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState = { autenticado: false, pode: () => false }
  })

  it('redireciona / para /login', async () => {
    const router = buildTestRouter()
    await router.push('/')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('redireciona /relatorios para /login', async () => {
    const router = buildTestRouter()
    await router.push('/relatorios')
    expect(router.currentRoute.value.path).toBe('/login')
  })
})

describe('Router guard - autenticado sem permissao', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState = {
      autenticado: true,
      pode: (permissao) => permissao === 'dashboard:read',
    }
  })

  it('redireciona /auditoria para /', async () => {
    const router = buildTestRouter()
    await router.push('/auditoria')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('redireciona /relatorios para /', async () => {
    const router = buildTestRouter()
    await router.push('/relatorios')
    expect(router.currentRoute.value.path).toBe('/')
  })
})

describe('Router guard - autenticado com permissao', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState = {
      autenticado: true,
      pode: () => true,
    }
  })

  it('permite /', async () => {
    const router = buildTestRouter()
    await router.push('/')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('permite /auditoria', async () => {
    const router = buildTestRouter()
    await router.push('/auditoria')
    expect(router.currentRoute.value.path).toBe('/auditoria')
  })

  it('permite /relatorios', async () => {
    const router = buildTestRouter()
    await router.push('/relatorios')
    expect(router.currentRoute.value.path).toBe('/relatorios')
  })
})
