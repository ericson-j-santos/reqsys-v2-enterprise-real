const fs = require('fs')
const path = require('path')
const { test, expect } = require('@playwright/test')
const AxeBuilder = require('@axe-core/playwright').default
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')

/**
 * Cobertura de acessibilidade (axe-core) para o catálogo completo de rotas.
 *
 * `tests/e2e/accessibility-visual.spec.ts` já cobre a página pública raiz
 * (login, via `npm run preview` sem backend). Esta suíte complementa cobrindo
 * as 36 rotas autenticadas do catálogo canônico, reaproveitando o mesmo mock
 * de API e login demo já usados por `responsividade.spec.js` — sem depender
 * de backend real.
 *
 * Padrão "ratchet": dívida de acessibilidade JÁ CONHECIDA (levantada na
 * primeira execução desta suíte, 2026-09-04) não bloqueia o merge — mas
 * qualquer violação NOVA, fora deste conjunto conhecido, falha o build.
 * Isso da visibilidade real à dívida sem introduzir um gate que já nasce
 * vermelho, e impede regressão adicional enquanto a dívida não é paga.
 *
 * Dívida sistêmica do shell: ZERADA em 2026-09-05.
 *
 * - aria-required-children / aria-required-parent: vinham do `<div class="v-
 *   list-group__items" role="group">` que a Vuetify cria via
 *   `_createElementVNode` literal dentro do `VListGroup.js` (sem prop pública
 *   pra sobrescrever) como filho direto de `<v-list role="list">` — e
 *   role="list" só aceita filho role="listitem". Como o role="group" não sai,
 *   o que saiu foi a afirmação de lista que a estrutura não sustentava: o
 *   `<v-list>` do menu passou a `role="presentation"`, o cabeçalho do tema a
 *   `role="button"` + `aria-expanded` (que é o que ele de fato é) e os itens
 *   voltaram ao `role="link"` que a própria Vuetify calcula para `:to`.
 *   Travado por `src/layouts/__tests__/AppLayoutAcessibilidade.test.js`, que
 *   roda axe sobre um recorte do menu em segundos — antes de reprovar a
 *   combinação antiga de papéis, para provar que o recorte é sensível.
 *
 * aria-tooltip-name: FECHADO em 2026-09-05. Os `<v-tooltip :text="...">` só
 * renderizam o texto quando ativos; com o tooltip fechado (estado padrão do
 * scanner) o `role="tooltip"` fica sem nome acessível, porque a Vuetify não
 * espelha `text` num `aria-label` estático. O shell compartilhado foi
 * corrigido nos PRs #1484/#1486 e as 10 telas restantes (49 tooltips locais)
 * neste incremento — sempre com `aria-label` no próprio `<v-tooltip>`, NÃO
 * com `:content-props="{ 'aria-label': ... }"`, que só alcança o
 * `.v-overlay__content` (filho) e não o elemento que carrega `role="tooltip"`
 * (o `.v-overlay` pai). Regressão barrada por
 * `npm run validate:tooltip-a11y`, que reprova qualquer `<v-tooltip>` com
 * texto e sem nome acessível.
 *
 * Além disso, violações menores e específicas de cada tela (contraste de
 * cor, botão sem texto acessível, progressbar sem nome, região com scroll
 * sem foco de teclado, controle interativo aninhado) — reais, de escopo
 * pequeno o bastante para tratar tela a tela depois. Essas ficam na
 * allowlist por PAR (rota, regra) — não por regra sozinha — para que uma
 * violação NOVA da mesma regra numa rota diferente ainda quebre o teste.
 */

// Zerada: nenhuma regra falha hoje em todas as rotas por causa do shell.
// Manter o conjunto vazio (em vez de remover o conceito) deixa explícito que
// qualquer violação sistêmica nova é regressão, não dívida herdada.
const REGRAS_SISTEMICAS_CONHECIDAS = new Set([])

const VIOLACOES_ESPECIFICAS_CONHECIDAS = new Set([
  '/home|color-contrast',
  '/workspace|color-contrast',
  '/ajuda|color-contrast',
  '/relatorios|button-name',
  '/qualidade-ia|aria-progressbar-name',
  '/recomendacoes-ia|button-name',
  '/task-console|button-name',
  '/task-console|scrollable-region-focusable',
  '/specs|color-contrast',
  '/painel-integracao|aria-progressbar-name',
  '/estatisticas|nested-interactive',
  '/figma-github|color-contrast',
  '/figma-github|scrollable-region-focusable',
])

function carregarRotasCanonicas() {
  const arquivo = path.resolve(__dirname, '../../src/constants/rotasResponsivas.js')
  const source = fs.readFileSync(arquivo, 'utf8')
  const pattern = /\{\s*path:\s*'([^']+)',\s*testId:\s*'([^']+)',\s*titulo:\s*'([^']+)'\s*\}/g
  return [...source.matchAll(pattern)].map((match) => ({
    path: match[1] === '/estatisticas/:indicadorId' ? '/estatisticas/total-requisitos' : match[1],
    testId: match[2],
    public: match[1] === '/login',
  }))
}

const ROTAS_AUTENTICADAS = carregarRotasCanonicas().filter((item) => !item.public)

test.describe('acessibilidade: catálogo completo de rotas autenticadas', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
  })

  test('nenhuma rota autenticada tem violação wcag NOVA (fora da dívida conhecida)', async ({ page }) => {
    test.setTimeout(600_000)
    await loginDemo(page)

    const violacoesNovasPorRota = {}
    const resumoDividaConhecida = {}

    for (const rota of ROTAS_AUTENTICADAS) {
      await test.step(rota.path, async () => {
        await page.goto(rota.path)
        await expect(page.getByTestId(rota.testId)).toBeVisible({ timeout: 15000 })

        const resultado = await new AxeBuilder({ page })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
          .analyze()

        const criticas = resultado.violations.filter((item) =>
          ['critical', 'serious'].includes(item.impact || ''),
        )

        const ehConhecida = (item) =>
          REGRAS_SISTEMICAS_CONHECIDAS.has(item.id) ||
          VIOLACOES_ESPECIFICAS_CONHECIDAS.has(`${rota.path}|${item.id}`)

        const novas = criticas.filter((item) => !ehConhecida(item))
        const conhecidas = criticas.filter((item) => ehConhecida(item))

        if (novas.length > 0) {
          violacoesNovasPorRota[rota.path] = novas.map((item) => ({
            id: item.id,
            impact: item.impact,
            ajuda: item.help,
            ocorrencias: item.nodes.length,
          }))
        }
        if (conhecidas.length > 0) {
          resumoDividaConhecida[rota.path] = conhecidas.map((item) => `${item.id} (${item.nodes.length}x)`)
        }
      })
    }

    await test.info().attach('divida-a11y-conhecida.json', {
      body: JSON.stringify(resumoDividaConhecida, null, 2),
      contentType: 'application/json',
    })

    expect(
      violacoesNovasPorRota,
      `Violações de acessibilidade NOVAS (fora das allowlists REGRAS_SISTEMICAS_CONHECIDAS/VIOLACOES_ESPECIFICAS_CONHECIDAS no topo deste arquivo): ${JSON.stringify(violacoesNovasPorRota, null, 2)}`,
    ).toEqual({})
  })
})
