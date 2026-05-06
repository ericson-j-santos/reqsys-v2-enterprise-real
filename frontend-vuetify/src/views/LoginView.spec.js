import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import LoginView from './LoginView.vue'

const mockLogin = vi.fn()

vi.mock('../stores/auth', () => ({
  useAuthStore: () => ({
    login: mockLogin,
    autenticado: false,
    usuario: null,
  }),
}))

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: { template: '<div>login</div>' } },
      { path: '/', component: { template: '<div>home</div>' } },
    ],
  })
}

async function mountLogin() {
  const router = buildRouter()
  await router.push('/login')
  const wrapper = mount(LoginView, {
    global: {
      plugins: [router],
      stubs: {
        'v-container': { template: '<div><slot /></div>' },
        'v-row': { template: '<div><slot /></div>' },
        'v-col': { template: '<div><slot /></div>' },
        'v-card': { template: '<div><slot /></div>' },
        'v-card-title': { template: '<div><slot /></div>' },
        'v-card-text': { template: '<div><slot /></div>' },
        'v-card-actions': { template: '<div><slot /></div>' },
        'v-divider': { template: '<hr />' },
        'v-icon': { template: '<i />' },
        'v-chip': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
        'v-alert': { template: '<div data-testid="v-alert"><slot /></div>' },
        'v-btn': {
          template: '<button :disabled="disabled || loading" :type="type || \'button\'" @click="$emit(\'click\')"><slot /></button>',
          props: ['loading', 'disabled', 'type'],
          emits: ['click'],
        },
        'v-form': { template: '<form><slot /></form>' },
        'v-text-field': {
          template: '<input :type="type || \'text\'" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          props: ['modelValue', 'type', 'label', 'errorMessages'],
          emits: ['update:modelValue'],
        },
      },
    },
  })

  return { wrapper, router }
}

describe('LoginView - renderizacao', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renderiza formulario com dois inputs', async () => {
    const { wrapper } = await mountLogin()
    expect(wrapper.findAll('input').length).toBeGreaterThanOrEqual(2)
  })

  it('inicia com credencial demo de admin', async () => {
    const { wrapper } = await mountLogin()
    expect(wrapper.vm.email).toBe('admin@reqsys.local')
    expect(wrapper.vm.senha).toBe('admin123')
  })
})

describe('LoginView - validacao', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('nao chama login quando email vazio', async () => {
    const { wrapper } = await mountLogin()
    wrapper.vm.email = ''
    wrapper.vm.senha = 'x'

    await wrapper.vm.efetuarLogin()
    expect(mockLogin).not.toHaveBeenCalled()
    expect(wrapper.vm.errors.email).toBe('Obrigatório')
  })

  it('nao chama login quando senha vazia', async () => {
    const { wrapper } = await mountLogin()
    wrapper.vm.email = 'admin@reqsys.local'
    wrapper.vm.senha = ''

    await wrapper.vm.efetuarLogin()
    expect(mockLogin).not.toHaveBeenCalled()
    expect(wrapper.vm.errors.senha).toBe('Obrigatório')
  })
})

describe('LoginView - login com sucesso', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('chama auth.login com email e senha', async () => {
    mockLogin.mockResolvedValueOnce(undefined)
    const { wrapper } = await mountLogin()

    wrapper.vm.email = 'admin@test.com'
    wrapper.vm.senha = 'senha123'
    await wrapper.vm.efetuarLogin()

    expect(mockLogin).toHaveBeenCalledWith('admin@test.com', 'senha123')
  })

  it('redireciona para / apos sucesso', async () => {
    mockLogin.mockResolvedValueOnce(undefined)
    const { wrapper, router } = await mountLogin()

    wrapper.vm.email = 'admin@test.com'
    wrapper.vm.senha = 'senha123'
    await wrapper.vm.efetuarLogin()
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/')
  })
})

describe('LoginView - erro de autenticacao', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('mostra detail retornado pela API', async () => {
    mockLogin.mockRejectedValueOnce({ response: { data: { detail: 'Credenciais invalidas' } } })
    const { wrapper } = await mountLogin()

    wrapper.vm.email = 'x@x.com'
    wrapper.vm.senha = 'errada'
    await wrapper.vm.efetuarLogin()

    expect(wrapper.vm.errMsg).toBe('Credenciais invalidas')
  })

  it('usa mensagem padrao sem detail', async () => {
    mockLogin.mockRejectedValueOnce(new Error('network'))
    const { wrapper } = await mountLogin()

    wrapper.vm.email = 'x@x.com'
    wrapper.vm.senha = 'errada'
    await wrapper.vm.efetuarLogin()

    expect(wrapper.vm.errMsg).toBe('Credenciais inválidas.')
  })
})

describe('LoginView - preencherDemo', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('atualiza email e senha com demo escolhido', async () => {
    const { wrapper } = await mountLogin()
    wrapper.vm.preencherDemo({ papel: 'Analista', email: 'analista@reqsys.local', senha: 'analista123' })

    expect(wrapper.vm.email).toBe('analista@reqsys.local')
    expect(wrapper.vm.senha).toBe('analista123')
  })
})
