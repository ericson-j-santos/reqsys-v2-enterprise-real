import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('../../services/api', () => ({
  api: { post: vi.fn(), get: vi.fn() },
}))

vi.mock('../../auth/certificate', () => ({
  loginWithCertificateAgent: vi.fn(),
}))

import { api } from '../../services/api'
import { loginWithCertificateAgent } from '../../auth/certificate'
import { useAuthStore } from '../auth'

const sessao = {
  access_token: 'jwt-token',
  usuario: {
    email: 'admin@example.com',
    nome: 'Admin',
    papel: 'admin',
    permissoes: ['dashboard:read', 'requisitos:write'],
  },
}

describe('stores/auth', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('inicia não autenticado quando não há token', () => {
    const auth = useAuthStore()
    expect(auth.autenticado).toBe(false)
    expect(auth.permissoes).toEqual([])
  })

  it('salvarSessao persiste token e usuário e marca autenticado', () => {
    const auth = useAuthStore()
    auth.salvarSessao(sessao)
    expect(auth.autenticado).toBe(true)
    expect(auth.token).toBe('jwt-token')
    expect(localStorage.getItem('reqsys_token')).toBe('jwt-token')
    expect(JSON.parse(localStorage.getItem('reqsys_usuario')).email).toBe('admin@example.com')
  })

  it('login chama POST /v1/auth/login e salva a sessão retornada', async () => {
    api.post.mockResolvedValueOnce({ data: { data: sessao } })
    const auth = useAuthStore()
    await auth.login({ email: 'admin@example.com', senha: 'x' })
    expect(api.post).toHaveBeenCalledWith('/v1/auth/login', { email: 'admin@example.com', senha: 'x' })
    expect(auth.autenticado).toBe(true)
  })

  it('pode() reflete as permissões do usuário', () => {
    const auth = useAuthStore()
    auth.salvarSessao(sessao)
    expect(auth.pode('requisitos:write')).toBe(true)
    expect(auth.pode('inexistente:acao')).toBe(false)
  })

  it('sair limpa estado e localStorage', () => {
    const auth = useAuthStore()
    auth.salvarSessao(sessao)
    auth.sair()
    expect(auth.autenticado).toBe(false)
    expect(auth.usuario).toBeNull()
    expect(localStorage.getItem('reqsys_token')).toBeNull()
    expect(localStorage.getItem('reqsys_usuario')).toBeNull()
  })

  it('corrige mojibake nos campos do usuário ao salvar a sessão', () => {
    const auth = useAuthStore()
    // "InvocaÃ§Ã£o" é o mojibake de "Invocação" quando UTF-8 é lido como latin-1.
    auth.salvarSessao({
      access_token: 't',
      usuario: { nome: 'AnÃ¡lise', email: 'a@b.com', papel: 'admin' },
    })
    expect(auth.usuario.nome).toBe('Análise')
  })
})
