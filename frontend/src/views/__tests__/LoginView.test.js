import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import LoginView from '../LoginView.vue'
import { loginMicrosoftRedirect } from '../../auth/msal'
import { POST_LOGIN_REDIRECT_KEY } from '../../auth/postLoginRedirect'

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

async function montarLogin(path = '/login') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: LoginView },
      { path: '/', component: { template: '<div />' } },
    ],
  })
  await router.push(path)
  await router.isReady()

  return mount(LoginView, {
    global: { plugins: [router] },
  })
}

describe('LoginView: carregamento da configuracao de autenticacao', () => {
  beforeEach(() => {
    apiGet.mockReset()
    vi.mocked(loginMicrosoftRedirect).mockReset()
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

  it('preserva o painel solicitado antes de iniciar o redirecionamento Microsoft', async () => {
    apiGet.mockResolvedValueOnce({
      data: {
        data: {
          azure_enabled: true,
          certificate_enabled: false,
          demo_login_enabled: false,
        },
      },
    })

    const wrapper = await montarLogin('/login?redirect=/painel-projetos')
    await flushPromises()
    const button = wrapper.findAll('button').find((item) => item.text().includes('Entrar com conta Microsoft'))
    expect(button).toBeTruthy()

    await button.trigger('click')
    await flushPromises()

    expect(sessionStorage.getItem(POST_LOGIN_REDIRECT_KEY)).toBe('/painel-projetos')
    expect(loginMicrosoftRedirect).toHaveBeenCalledOnce()
    wrapper.unmount()
  })
})
