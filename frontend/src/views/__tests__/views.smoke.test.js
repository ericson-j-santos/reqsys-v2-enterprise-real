import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

// Mock "flexível" da API: qualquer acesso encadeado funciona e os métodos de
// array (map/filter/...) retornam vazio. Assim o onMounted de cada view roda
// sem quebrar, independentemente do formato esperado da resposta.
// vi.hoisted garante que os helpers existam quando a factory de vi.mock roda.
const { respostaApi } = vi.hoisted(() => {
  function flexible() {
    const base = function () {}
    return new Proxy(base, {
      get(_target, prop) {
        if (prop === 'then') return undefined
        if (prop === Symbol.iterator) return Array.prototype[Symbol.iterator].bind([])
        if (prop === 'length') return 0
        if (typeof Array.prototype[prop] === 'function') {
          return Array.prototype[prop].bind([])
        }
        return flexible()
      },
      apply() {
        return flexible()
      },
    })
  }
  return { respostaApi: () => ({ data: { data: flexible() } }) }
})

vi.mock('../../services/api', () => ({
  api: {
    get: vi.fn().mockResolvedValue(respostaApi()),
    post: vi.fn().mockResolvedValue(respostaApi()),
    put: vi.fn().mockResolvedValue(respostaApi()),
    delete: vi.fn().mockResolvedValue(respostaApi()),
  },
}))

// Evita que erros assíncronos de lifecycle quebrem o smoke test — queremos
// apenas garantir que cada view monta e renderiza um nó raiz.
const config = { warnHandler: () => {} }

function criarRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
}

const modulos = import.meta.glob('../*.vue', { eager: true })

describe('Smoke test — todas as views montam sem erro', () => {
  const entradas = Object.entries(modulos)
  expect(entradas.length).toBeGreaterThan(0)

  it.each(entradas)('monta %s', async (caminho, modulo) => {
    const Componente = modulo.default
    const router = criarRouter()
    router.push('/')
    await router.isReady()

    const wrapper = mount(Componente, {
      shallow: true,
      global: {
        plugins: [router],
        config,
      },
    })

    expect(wrapper.exists()).toBe(true)
    expect(typeof wrapper.html()).toBe('string')
    wrapper.unmount()
  })
})
