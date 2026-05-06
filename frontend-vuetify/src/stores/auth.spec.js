/**
 * Testes unitários do Pinia store de autenticação (auth.js)
 * Cobre: estado inicial, login, sair, autenticado, pode()
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mocka o módulo api ANTES de importar o store
vi.mock('../services/api', () => ({
  default: { post: vi.fn() }
}))

import { useAuthStore } from './auth'
import api from '../services/api'

const mockUsuario = (papel = 'admin', permissoes = ['dashboard:read', 'auditoria:read']) => ({
  nome: 'Test User',
  email: `${papel}@test.com`,
  papel,
  permissoes,
})

const mockLoginResponse = (papel = 'admin') => ({
  data: {
    access_token: `token-${papel}-123`,
    usuario: mockUsuario(papel, papel === 'admin'
      ? ['dashboard:read', 'auditoria:read', 'relatorios:read']
      : ['dashboard:read']),
  },
})

// ----------------------------------------------------------------------------
// Estado inicial
// ----------------------------------------------------------------------------
describe('useAuthStore – estado inicial', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('token é null quando localStorage está vazio', () => {
    const store = useAuthStore()
    expect(store.token).toBeNull()
  })

  it('autenticado é false sem token', () => {
    const store = useAuthStore()
    expect(store.autenticado).toBe(false)
  })

  it('usuario é null no estado inicial', () => {
    const store = useAuthStore()
    expect(store.usuario).toBeNull()
  })

  it('carrega token persistido do localStorage ao criar o store', () => {
    localStorage.setItem('reqsys_token', 'persisted-token')
    const store = useAuthStore()
    expect(store.token).toBe('persisted-token')
    expect(store.autenticado).toBe(true)
  })
})

// ----------------------------------------------------------------------------
// login()
// ----------------------------------------------------------------------------
describe('useAuthStore – login()', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('grava o token no store após login bem-sucedido', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('admin'))
    const store = useAuthStore()
    await store.login('admin@test.com', 'senha123')
    expect(store.token).toBe('token-admin-123')
  })

  it('persiste o token no localStorage', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('admin'))
    const store = useAuthStore()
    await store.login('admin@test.com', 'senha123')
    expect(localStorage.getItem('reqsys_token')).toBe('token-admin-123')
  })

  it('marca autenticado como true após login', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('admin'))
    const store = useAuthStore()
    await store.login('admin@test.com', 'senha123')
    expect(store.autenticado).toBe(true)
  })

  it('popula os dados do usuário após login', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('analista'))
    const store = useAuthStore()
    await store.login('analista@test.com', 'senha123')
    expect(store.usuario).not.toBeNull()
    expect(store.usuario.papel).toBe('analista')
    expect(store.usuario.email).toBe('analista@test.com')
  })

  it('chama api.post com endpoint e credenciais corretas', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('admin'))
    const store = useAuthStore()
    await store.login('admin@test.com', 'pw123')
    expect(api.post).toHaveBeenCalledWith('/v1/auth/login', { email: 'admin@test.com', senha: 'pw123' })
  })

  it('lança o erro quando a API retorna falha', async () => {
    const apiError = new Error('Credenciais inválidas')
    api.post.mockRejectedValueOnce(apiError)
    const store = useAuthStore()
    await expect(store.login('x@x.com', 'errada')).rejects.toThrow('Credenciais inválidas')
  })

  it('não grava token quando login falha', async () => {
    api.post.mockRejectedValueOnce(new Error('401'))
    const store = useAuthStore()
    try { await store.login('x@x.com', 'errada') } catch {}
    expect(store.token).toBeNull()
    expect(localStorage.getItem('reqsys_token')).toBeNull()
  })
})

// ----------------------------------------------------------------------------
// sair()
// ----------------------------------------------------------------------------
describe('useAuthStore – sair()', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('limpa token do store', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('admin'))
    const store = useAuthStore()
    await store.login('admin@test.com', 'senha')
    store.sair()
    expect(store.token).toBeNull()
  })

  it('limpa usuário do store', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('admin'))
    const store = useAuthStore()
    await store.login('admin@test.com', 'senha')
    store.sair()
    expect(store.usuario).toBeNull()
  })

  it('remove token do localStorage', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('admin'))
    const store = useAuthStore()
    await store.login('admin@test.com', 'senha')
    store.sair()
    expect(localStorage.getItem('reqsys_token')).toBeNull()
  })

  it('marca autenticado como false após sair', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('admin'))
    const store = useAuthStore()
    await store.login('admin@test.com', 'senha')
    store.sair()
    expect(store.autenticado).toBe(false)
  })
})

// ----------------------------------------------------------------------------
// pode()
// ----------------------------------------------------------------------------
describe('useAuthStore – pode()', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('retorna true quando o usuário tem a permissão', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('admin'))
    const store = useAuthStore()
    await store.login('admin@test.com', 'senha')
    expect(store.pode('auditoria:read')).toBe(true)
  })

  it('retorna false quando o usuário não tem a permissão', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('analista'))
    const store = useAuthStore()
    await store.login('analista@test.com', 'senha')
    expect(store.pode('auditoria:read')).toBe(false)
  })

  it('retorna false quando não há usuário logado', () => {
    const store = useAuthStore()
    expect(store.pode('dashboard:read')).toBe(false)
  })

  it('admin tem acesso ao dashboard', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('admin'))
    const store = useAuthStore()
    await store.login('admin@test.com', 'senha')
    expect(store.pode('dashboard:read')).toBe(true)
  })

  it('analista não tem acesso à auditoria', async () => {
    api.post.mockResolvedValueOnce(mockLoginResponse('analista'))
    const store = useAuthStore()
    await store.login('analista@test.com', 'senha')
    expect(store.pode('auditoria:read')).toBe(false)
  })
})
