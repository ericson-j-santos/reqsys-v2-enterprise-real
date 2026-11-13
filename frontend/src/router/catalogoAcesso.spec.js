import { beforeEach, describe, expect, it, vi } from 'vitest'

const { auth } = vi.hoisted(() => ({
  auth: {
    autenticado: false,
    usuario: null,
    pode: vi.fn(),
    atualizarSessao: vi.fn(),
  },
}))

vi.mock('../stores/auth', () => ({ useAuthStore: () => auth }))

import router from './index'

describe('Proteção real de navegação do catálogo no ReqSys', () => {
  beforeEach(async () => {
    auth.autenticado = false
    auth.usuario = null
    auth.pode.mockReset().mockImplementation(recurso => auth.usuario?.permissoes?.includes(recurso) === true)
    auth.atualizarSessao.mockReset()
    await router.push('/login')
    await router.isReady()
  })

  it('nega acesso anônimo e mantém o destino de retorno para login', async () => {
    await router.push('/painel-projetos')
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/painel-projetos')
  })

  it('nega token armazenado sem identidade quando atualização falha', async () => {
    auth.autenticado = true
    auth.usuario = null
    auth.atualizarSessao.mockRejectedValue(new Error('serviço indisponível'))
    await router.push('/painel-projetos')
    expect(auth.atualizarSessao).toHaveBeenCalledTimes(1)
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.reset).toBe('security')
  })

  it('admite apenas identidade com dashboard:read explícito', async () => {
    auth.autenticado = true
    auth.usuario = { permissoes: ['dashboard:read'] }
    await router.push('/painel-projetos')
    expect(router.currentRoute.value.path).toBe('/painel-projetos')
    expect(auth.atualizarSessao).not.toHaveBeenCalled()
  })

  it('bloqueia usuário sem dashboard:read sem redirecionamento circular', async () => {
    auth.autenticado = true
    auth.usuario = { permissoes: ['requisitos:write'] }
    auth.atualizarSessao.mockRejectedValue(new Error('sem permissão'))
    await router.push('/painel-projetos')
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.reset).toBe('security')
  })

  it('preserva aviso de falta de permissão quando dashboard:read está presente', async () => {
    auth.autenticado = true
    auth.usuario = { permissoes: ['dashboard:read'] }
    auth.atualizarSessao.mockRejectedValue(new Error('sem papel admin'))
    await router.push('/admin/ocr-review')
    expect(router.currentRoute.value.path).toBe('/')
    expect(router.currentRoute.value.query.forbidden).toBe('ocr-review:admin')
  })
})
