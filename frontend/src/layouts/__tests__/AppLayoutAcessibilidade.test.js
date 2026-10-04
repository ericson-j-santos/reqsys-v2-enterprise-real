/**
 * Regressão de acessibilidade da navegação lateral.
 *
 * Contexto: `tests/e2e/acessibilidade-rotas.spec.js` cobre as 36 rotas com
 * Playwright, mas leva ~5 minutos e depende de build + login demo. Como
 * `aria-required-children`/`aria-required-parent` nasciam da estrutura do
 * shell — e não do conteúdo de cada tela — dá para travar a correção aqui,
 * em segundos.
 *
 * A causa raiz era a combinação de três papéis ARIA incompatíveis entre si:
 *
 * - `<v-list>` declarava `role="list"`, que só aceita filhos `role="listitem"`;
 * - `<v-list-group>` injeta um `<div class="v-list-group__items" role="group">`
 *   via `_createElementVNode` literal dentro do VListGroup.js da Vuetify — sem
 *   prop pública para sobrescrever, logo aquele `role="list"` sempre teria um
 *   filho proibido;
 * - os itens aninhados recebiam `role="listitem"` explícito, mas o pai deles é
 *   justamente aquele `role="group"`, e `listitem` exige um `list` como
 *   contexto.
 *
 * A saída não é remover o `role="group"` (não dá), e sim parar de afirmar uma
 * semântica de lista que a estrutura não sustenta: o menu vira `presentation`,
 * o cabeçalho do tema assume `role="button"` + `aria-expanded` (é o que ele de
 * fato é) e os itens voltam ao `role="link"` que a própria Vuetify calcula
 * para `:to`. O `<div role="group" aria-labelledby>` passa então a ser
 * exatamente o que diz ser: um grupo de links rotulado pelo tema.
 *
 * Divisão dos testes deste arquivo:
 *
 * - os primeiros montam o AppLayout real e travam os papéis aplicados;
 * - o último roda axe-core sobre um recorte isolado da mesma estrutura de
 *   `<v-list-group>`. O recorte é necessário porque, dentro do
 *   `<v-navigation-drawer>` e sem o CSS da Vuetify, o jsdom não expõe o menu
 *   como visível e o axe marca `aria-required-children` como *inapplicable* —
 *   ou seja, rodar axe no AppLayout inteiro aqui passaria mesmo com o bug. O
 *   próprio teste prova que o recorte é sensível, reprovando a combinação
 *   antiga de papéis antes de aprovar a nova.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { createPinia, setActivePinia } from 'pinia'
import axe from 'axe-core'
import AppLayout from '../AppLayout.vue'

vi.mock('../../services/api', () => ({
  api: { get: vi.fn().mockResolvedValue({ data: { data: {} } }) },
}))

vi.mock('../../composables/navPendencias', () => ({
  carregarDadosPendenciasNav: vi.fn().mockResolvedValue({}),
}))

function novoRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
}

function montar(componente) {
  return mount(componente, {
    attachTo: document.body,
    global: { plugins: [createVuetify({ components, directives }), novoRouter()] },
  })
}

/**
 * Recorte do menu do AppLayout: um `<v-list-group>` com cabeçalho e itens
 * aninhados, parametrizado pelos papéis ARIA para que o teste possa comparar
 * a combinação antiga com a nova.
 */
function recorteDoMenu({ listRole, activatorRole, itemRole }) {
  return {
    components: { VList: components.VList, VListGroup: components.VListGroup, VListItem: components.VListItem },
    template: `
      <nav>
        <v-list :opened="['tema']" density="compact" nav aria-label="Navegacao por temas expansiveis"
                ${listRole ? `role="${listRole}"` : ''}>
          <v-list-group value="tema">
            <template #activator="{ props, isOpen }">
              <v-list-item v-bind="props" ${activatorRole ? `role="${activatorRole}"` : ''}
                           :aria-expanded="isOpen" :aria-selected="undefined" title="Tema" />
            </template>
            <div class="nav-subgroup-stack">
              <div class="nav-subgroup">
                <button class="nav-subgroup-header" type="button">Subgrupo</button>
                <v-list-item ${itemRole ? `role="${itemRole}"` : ''} to="/a" title="Item A" />
              </div>
            </div>
            <v-list-item ${itemRole ? `role="${itemRole}"` : ''} to="/b" title="Item B" />
          </v-list-group>
        </v-list>
      </nav>`,
  }
}

async function regrasVioladas(componente) {
  const wrapper = montar(componente)
  await wrapper.vm.$nextTick()
  const resultado = await axe.run(document.body, {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] },
  })
  wrapper.unmount()
  return resultado.violations
    .filter((item) => ['critical', 'serious'].includes(item.impact))
    .map((item) => item.id)
}

describe('AppLayout: acessibilidade da navegação lateral', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
  })

  it('não declara semântica de lista que a estrutura do VListGroup não sustenta', async () => {
    const wrapper = montar(AppLayout)
    await wrapper.vm.$nextTick()

    const menu = document.querySelector('.req-nav-list')
    expect(menu, 'menu de temas deve estar montado').not.toBeNull()
    expect(menu.getAttribute('role')).toBe('presentation')

    // O <div role="group"> da Vuetify continua lá — não há como removê-lo.
    // O que muda é que ele deixou de ser filho ilegal de um role="list".
    expect(document.querySelector('.v-list-group__items')?.getAttribute('role')).toBe('group')

    wrapper.unmount()
  })

  it('descreve o cabeçalho do tema como controle de expandir/recolher', async () => {
    const wrapper = montar(AppLayout)
    await wrapper.vm.$nextTick()

    const cabecalhos = [...document.querySelectorAll('.nav-theme-item')]
    expect(cabecalhos.length).toBeGreaterThan(0)
    for (const cabecalho of cabecalhos) {
      expect(cabecalho.getAttribute('role')).toBe('button')
      expect(cabecalho.getAttribute('aria-expanded')).toMatch(/^(true|false)$/)
    }

    wrapper.unmount()
  })

  it('mantém os itens de navegação como links, sem role="listitem" forçado', async () => {
    const wrapper = montar(AppLayout)
    await wrapper.vm.$nextTick()

    const itens = [...document.querySelectorAll('.nav-item--nested')]
    expect(itens.length).toBeGreaterThan(0)
    for (const item of itens) {
      expect(item.getAttribute('role')).not.toBe('listitem')
    }

    wrapper.unmount()
  })

  it('a combinação antiga de papéis reprova no axe e a nova passa', async () => {
    const antiga = await regrasVioladas(
      recorteDoMenu({ listRole: null, activatorRole: 'listitem', itemRole: 'listitem' }),
    )
    expect(antiga, 'o recorte precisa ser sensível ao bug, senão o teste abaixo não prova nada')
      .toEqual(expect.arrayContaining(['aria-required-children', 'aria-required-parent']))

    const nova = await regrasVioladas(
      recorteDoMenu({ listRole: 'presentation', activatorRole: 'button', itemRole: null }),
    )
    expect(nova).toEqual([])
  }, 30_000)
})
