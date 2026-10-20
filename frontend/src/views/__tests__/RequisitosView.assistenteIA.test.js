import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import RequisitosView from '../RequisitosView.vue'

const { apiPost, store, replace } = vi.hoisted(() => ({
  apiPost: vi.fn(),
  replace: vi.fn(),
  store: {
    itens: [],
    carregando: false,
    erro: '',
    listar: vi.fn().mockResolvedValue(),
    criar: vi.fn().mockResolvedValue(),
  },
}))

vi.mock('../../services/api', () => ({ api: { post: apiPost } }))
vi.mock('../../stores/requisitos', () => ({ useRequisitosStore: () => store }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { acao: 'novo' } }),
  useRouter: () => ({ replace }),
}))

const Slot = { template: '<div><slot /></div>' }
const Field = {
  props: ['modelValue', 'label'],
  emits: ['update:modelValue'],
  template: '<label>{{ label }}<input :aria-label="label" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /></label>',
}
const Select = {
  props: ['modelValue', 'label', 'items'],
  emits: ['update:modelValue'],
  template: '<label>{{ label }}<select :aria-label="label" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="(item, index) in items" :key="index" :value="typeof item === \'string\' ? item : item.value">{{ typeof item === \'string\' ? item : item.label }}</option></select></label>',
}
const stubs = {
  VTooltip: { template: '<span><slot name="activator" :props="{}" /></span>' },
  VDialog: {
    props: ['modelValue'],
    template: '<div v-if="modelValue" data-formulario><slot /></div>',
  },
  VTextField: Field,
  VTextarea: Field,
  VSelect: Select,
  VBtn: {
    props: ['disabled', 'loading'],
    template: '<button :disabled="disabled || loading"><slot /></button>',
  },
  VAlert: {
    props: ['type'],
    template: '<div :data-alert-type="type"><slot /></div>',
  },
  ExpandTransition: Slot,
  VExpandTransition: Slot,
  VCard: Slot,
  VCardTitle: Slot,
  VCardText: Slot,
  VCardActions: Slot,
  VRow: Slot,
  VCol: Slot,
  VSpacer: Slot,
  VChip: Slot,
}

function resposta(data, success = true) {
  return { data: { success, data, errors: [], meta: {} } }
}

function pendente() {
  let resolve
  const promise = new Promise((resolver) => { resolve = resolver })
  return { promise, resolve }
}

let wrapper

function formulario() {
  return wrapper.get('[data-formulario]')
}

function campo(label) {
  return formulario().get('[aria-label="' + label + '"]')
}

function botao(label) {
  const encontrado = wrapper.findAll('button')
    .find((item) => item.text().trim() === label)
  expect(encontrado).toBeTruthy()
  return encontrado
}

async function montar() {
  wrapper = shallowMount(RequisitosView, { global: { stubs } })
  await flushPromises()
  await campo('Título').setValue('Requisito de teste')
  await campo('Descrição').setValue('Descrição original que precisa ser preservada.')
  await campo('Urgência').setValue('alta')
}

function configurarRespostas(urgencia) {
  apiPost.mockImplementation((path) => {
    if (path === '/v1/ia/sugerir-descricao') {
      return Promise.resolve(resposta({ descricao_sugerida: 'Descrição sugerida válida.' }))
    }
    if (path === '/v1/ia/classificar-urgencia') {
      return typeof urgencia === 'function' ? urgencia() : Promise.resolve(urgencia)
    }
    throw new Error('Rota inesperada no teste: ' + path)
  })
}

describe('RequisitosView: classificação de urgência segura', () => {
  beforeEach(() => {
    apiPost.mockReset()
    store.listar.mockClear()
    store.criar.mockClear()
    replace.mockClear()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
  })

  it('aplica resposta válida pelo cliente API compartilhado', async () => {
    configurarRespostas(resposta({
      urgencia: 'critica',
      justificativa: 'Interrupção confirmada do serviço.',
      provedor: 'gemini',
    }))
    await montar()
    await botao('Assistente IA').trigger('click')
    await flushPromises()

    expect(campo('Urgência').element.value).toBe('critica')
    expect(formulario().get('[data-alert-type="success"]').text())
      .toContain('Interrupção confirmada')
    expect(apiPost).toHaveBeenCalledWith('/v1/ia/classificar-urgencia', {
      titulo: 'Requisito de teste',
      descricao: 'Descrição original que precisa ser preservada.',
    })
  })

  it('mostra erro 502 e preserva urgência no formulário e no salvamento', async () => {
    configurarRespostas(() => Promise.reject({
      response: {
        status: 502,
        data: { detail: { code: 'IA_CLASSIFICACAO_INVALIDA', message: 'Resposta inválida.' } },
      },
    }))
    await montar()
    await botao('Assistente IA').trigger('click')
    await flushPromises()

    expect(campo('Urgência').element.value).toBe('alta')
    expect(campo('Descrição').element.value).toBe('Descrição sugerida válida.')
    expect(formulario().text()).toContain('classificação válida de urgência')
    expect(formulario().find('[data-alert-type="success"]').exists()).toBe(false)

    await botao('Salvar').trigger('click')
    await flushPromises()
    expect(store.criar).toHaveBeenCalledWith(expect.objectContaining({ urgencia: 'alta' }))
  })

  it.each([
    ['categoria desconhecida', { urgencia: 'urgente', justificativa: 'Motivo.' }],
    ['categoria ausente', { justificativa: 'Motivo.' }],
    ['justificativa vazia', { urgencia: 'media', justificativa: '   ' }],
    ['justificativa ausente', { urgencia: 'media' }],
  ])('rejeita HTTP 200 com %s', async (_nome, dados) => {
    configurarRespostas(resposta(dados))
    await montar()
    await botao('Assistente IA').trigger('click')
    await flushPromises()

    expect(campo('Urgência').element.value).toBe('alta')
    expect(formulario().text()).toContain('urgência preenchida foi mantida')
    expect(formulario().find('[data-alert-type="success"]').exists()).toBe(false)
  })

  it('não trata envelope success=false como classificação válida', async () => {
    configurarRespostas(resposta({
      urgencia: 'media',
      justificativa: 'Não deve ser aplicada.',
    }, false))
    await montar()
    await botao('Assistente IA').trigger('click')
    await flushPromises()

    expect(campo('Urgência').element.value).toBe('alta')
    expect(formulario().find('[data-alert-type="success"]').exists()).toBe(false)
  })

  it('preserva edição da descrição e descarta sugestões atrasadas', async () => {
    const consulta = pendente()
    configurarRespostas(() => consulta.promise)
    await montar()
    await botao('Assistente IA').trigger('click')
    await campo('Descrição').setValue('Descrição revisada manualmente.')
    consulta.resolve(resposta({
      urgencia: 'baixa',
      justificativa: 'Sugestão produzida para o conteúdo anterior.',
    }))
    await flushPromises()

    expect(campo('Descrição').element.value).toBe('Descrição revisada manualmente.')
    expect(campo('Urgência').element.value).toBe('alta')
    expect(formulario().text()).toContain('sugestões foram descartadas')
  })

  it('preserva urgência alterada manualmente durante a consulta', async () => {
    const consulta = pendente()
    configurarRespostas(() => consulta.promise)
    await montar()
    await botao('Assistente IA').trigger('click')
    await campo('Urgência').setValue('critica')
    consulta.resolve(resposta({ urgencia: 'baixa', justificativa: 'Sugestão anterior.' }))
    await flushPromises()

    expect(campo('Urgência').element.value).toBe('critica')
    expect(formulario().text()).toContain('sua escolha foi mantida')
    expect(formulario().find('[data-alert-type="success"]').exists()).toBe(false)
  })

  it('ignora resposta antiga depois de cancelar e reabrir o formulário', async () => {
    const consulta = pendente()
    configurarRespostas(() => consulta.promise)
    await montar()
    await botao('Assistente IA').trigger('click')
    await botao('Cancelar').trigger('click')
    await botao('Novo requisito').trigger('click')
    await campo('Descrição').setValue('Conteúdo do formulário reaberto.')
    await campo('Urgência').setValue('critica')

    consulta.resolve(resposta({
      urgencia: 'baixa',
      justificativa: 'Resposta pertencente ao formulário cancelado.',
    }))
    await flushPromises()

    expect(campo('Descrição').element.value).toBe('Conteúdo do formulário reaberto.')
    expect(campo('Urgência').element.value).toBe('critica')
    expect(formulario().find('[data-alert-type="success"]').exists()).toBe(false)
  })

  it('não encerra consulta nova quando uma resposta cancelada chega', async () => {
    const antiga = pendente()
    const nova = pendente()
    let chamadas = 0
    configurarRespostas(() => (++chamadas === 1 ? antiga.promise : nova.promise))
    await montar()
    await botao('Assistente IA').trigger('click')
    await botao('Cancelar').trigger('click')
    await botao('Novo requisito').trigger('click')
    await botao('Assistente IA').trigger('click')

    antiga.resolve(resposta({ urgencia: 'baixa', justificativa: 'Consulta antiga.' }))
    await flushPromises()
    expect(botao('Assistente IA').element.disabled).toBe(true)
    expect(campo('Urgência').element.value).toBe('alta')

    nova.resolve(resposta({ urgencia: 'critica', justificativa: 'Consulta atual.' }))
    await flushPromises()
    expect(botao('Assistente IA').element.disabled).toBe(false)
    expect(campo('Urgência').element.value).toBe('critica')
    expect(formulario().text()).toContain('Consulta atual.')
  })

  it('invalida sugestão pendente ao salvar sem alterar o payload', async () => {
    const consulta = pendente()
    configurarRespostas(() => consulta.promise)
    await montar()
    await botao('Assistente IA').trigger('click')
    await botao('Salvar').trigger('click')
    await flushPromises()

    consulta.resolve(resposta({ urgencia: 'baixa', justificativa: 'Resposta atrasada.' }))
    await flushPromises()
    await botao('Novo requisito').trigger('click')

    expect(store.criar).toHaveBeenCalledTimes(1)
    expect(store.criar).toHaveBeenCalledWith(expect.objectContaining({
      urgencia: 'alta',
      descricao: 'Descrição original que precisa ser preservada.',
    }))
    expect(campo('Urgência').element.value).toBe('alta')
    expect(campo('Descrição').element.value)
      .toBe('Descrição original que precisa ser preservada.')
  })

  it('mantém descrição se ela falhar e ainda aplica urgência válida', async () => {
    apiPost.mockImplementation((path) => {
      if (path === '/v1/ia/sugerir-descricao') return Promise.reject(new Error('Indisponível'))
      return Promise.resolve(resposta({ urgencia: 'critica', justificativa: 'Impacto elevado.' }))
    })
    await montar()
    await botao('Assistente IA').trigger('click')
    await flushPromises()

    expect(campo('Descrição').element.value)
      .toBe('Descrição original que precisa ser preservada.')
    expect(campo('Urgência').element.value).toBe('critica')
    expect(formulario().text()).toContain('descrição preenchida foi mantida')
  })
})
