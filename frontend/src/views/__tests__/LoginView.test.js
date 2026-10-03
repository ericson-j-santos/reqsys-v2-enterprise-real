import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import LoginView from '../LoginView.vue'

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }))

vi.mock('../../services/api', () => ({
  api: { get: apiGet },
}))

vi.mock('../../auth/msal', () => ({
  loginMicrosoftRedirect: vi.fn(),
}))

function requisicaoPendente() {
  let resolve
  const promise = new Promise((resolver) => {
    resolve = resolver
  })
  return { promise, resolve }
}

async function montarLogin() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: LoginView },
      { path: '/', component: { template: '<div />' } },
    ],
  })
  await router.push('/login')
  await router.isReady()

  return mount(LoginView, {
    global: { plugins: [router] },
  })
}

describe('LoginView: carregamento da configuracao de autenticacao', () => {
  beforeEach(() => {
    apiGet.mockReset()
    localStorage.clear()
    sessionStorage.clear()
  })

  it('exibe estado neutro durante a consulta sem anunciar indisponibilidade', async () => {
    const request = requisicaoPendente()
    apiGet.mockReturnValueOnce(request.promise)

    const wrapper = await montarLogin()

    expect(wrapper.get('[data-testid="auth-config-loading"]').text())
      .toContain('Verificando a autenticacao corporativa')
    expect(wrapper.find('[data-testid="auth-config-unavailable"]').exists()).toBe(false)

    request.resolve({
      data: {
        data: {
          azure_enabled: true,
          certificate_enabled: false,
          demo_login_enabled: false,
        },
      },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="auth-config-loading"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Entrar com conta Microsoft')
    expect(wrapper.find('[data-testid="auth-config-unavailable"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('mantem o aviso de indisponibilidade quando a configuracao desabilita todos os metodos', async () => {
    apiGet.mockResolvedValueOnce({
      data: {
        data: {
          azure_enabled: false,
          certificate_enabled: false,
          demo_login_enabled: false,
          operator_action: 'Configure o Microsoft Entra ID no servidor.',
        },
      },
    })

    const wrapper = await montarLogin()
    await flushPromises()

    expect(wrapper.find('[data-testid="auth-config-loading"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="auth-config-unavailable"]').text())
      .toContain('Autenticacao corporativa indisponivel')
    expect(wrapper.text()).toContain('Configure o Microsoft Entra ID no servidor.')
    wrapper.unmount()
  })

  it('mantem o erro real quando a consulta de configuracao falha', async () => {
    apiGet.mockRejectedValueOnce(new Error('falha de rede'))

    const wrapper = await montarLogin()
    await flushPromises()

    expect(wrapper.find('[data-testid="auth-config-loading"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="auth-config-unavailable"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Nao foi possivel obter a configuracao de autenticacao do servidor.')
    wrapper.unmount()
  })

  it('preserva o erro OAuth capturado quando a consulta de configuracao tambem falha', async () => {
    sessionStorage.setItem('azure_login_error', 'Acesso Microsoft cancelado pelo usuario.')
    apiGet.mockRejectedValueOnce(new Error('falha de rede'))

    const wrapper = await montarLogin()
    await flushPromises()

    expect(wrapper.find('[data-testid="auth-config-loading"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="auth-config-unavailable"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Acesso Microsoft cancelado pelo usuario.')
    expect(wrapper.text()).not.toContain('Nao foi possivel obter a configuracao')
    wrapper.unmount()
  })
})
