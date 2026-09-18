// Setup global para os testes unitários (Vitest + @vue/test-utils).
// Fornece polyfills do jsdom exigidos pelo Vuetify e um helper de montagem
// que registra Vuetify e Pinia em cada componente testado.
import { config } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, vi } from 'vitest'

// Polyfills que o Vuetify espera no ambiente jsdom.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }))
}

if (!window.visualViewport) {
  window.visualViewport = {
    width: 1024,
    height: 768,
    addEventListener: () => {},
    removeEventListener: () => {},
  }
}

const vuetify = createVuetify({ components, directives })

// Disponibiliza o plugin Vuetify para todos os mounts via test-utils.
config.global.plugins = [vuetify]

// Cada teste começa com uma instância Pinia limpa e ativa.
beforeEach(() => {
  setActivePinia(createPinia())
})
