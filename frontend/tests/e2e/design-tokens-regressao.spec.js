const fs = require('fs')
const path = require('path')
const { test, expect } = require('@playwright/test')
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')

/**
 * Regressão automatizada para os dois bugs reais reportados no levantamento de
 * layout/tooltip/tabela (2026-09-03) e corrigidos nos PRs #1473/#1477:
 *
 * 1) Tooltip coberto: dois problemas empilhados.
 *    a) VOverlay só teleporta para `.v-overlay-container` no <body> quando
 *       `attach === false` explicitamente — não quando fica apenas "não
 *       definido" (o padrão de VTooltip). Sem isso, o tooltip renderizava
 *       `position:absolute` inline dentro da árvore do componente, sujeito à
 *       ordem normal de pintura entre irmãos no DOM em vez de um stacking
 *       context de overlay real.
 *    b) VOverlay usa zIndex padrão 2000 e VTooltip roda com
 *       `_disableGlobalStack`, então mesmo teleportado ele nunca subia
 *       sozinho acima de overlays do app (toast/alerta de conectividade/
 *       aviso de rota, antes em 3000-9999 sem escala).
 *    Corrigido com `VTooltip: { attach: false, zIndex: DSC_Z_INDEX.tooltip }`
 *    (6000, topo da escala nomeada) no `defaults:` do createVuetify().
 *
 * 2) Densidade de tabela inconsistente: cada tela escolhia `density` sozinha.
 *    Corrigido com `defaults: { VDataTable: { density: DSC_TABLE.density } }`
 *    + `font-size: var(--table-row-font-size)` global em `.v-data-table`.
 *
 * Reaproveita o catálogo canônico de rotas e o mock de API já usados por
 * `responsividade.spec.js`, então cobre as mesmas 36 rotas autenticadas.
 */

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

test.describe('regressão: tooltip coberto por overlay do app', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
  })

  for (const rota of ['/', '/pipeline']) {
    test(`tooltip do menu lateral fica visível e acima de outros overlays em ${rota}`, async ({ page }) => {
      await loginDemo(page)
      await page.goto(rota)
      await expect(page.getByTestId('sidebar-toggle')).toBeVisible()

      await page.getByTestId('sidebar-toggle').hover()

      const tooltip = page.locator('.v-overlay--active.v-tooltip .v-overlay__content').first()
      await expect(tooltip, 'Tooltip não renderizou como ativo ao passar o mouse').toBeVisible({ timeout: 5000 })

      // Nota deliberada: não usamos elementFromPoint/elementsFromPoint aqui.
      // O conteúdo do tooltip roda com `pointer-events: none` por design (um
      // tooltip não deve bloquear clique no que está embaixo dele) — e tanto
      // elementFromPoint quanto elementsFromPoint IGNORAM elementos com
      // pointer-events:none no hit-test, então sempre "acham" que o tooltip
      // está coberto mesmo quando ele está pintado corretamente por cima.
      // A checagem correta e determinística é comparar z-index diretamente:
      // com CSS válido, um elemento posicionado com z-index explícito sempre
      // pinta acima de conteúdo `position:static`/`z-index:auto` no mesmo
      // contexto de empilhamento real — não depende de hit-testing.
      const teleportadoParaOverlayContainer = await tooltip.evaluate((el) =>
        Boolean(el.closest('.v-overlay-container') === document.body.querySelector(':scope > .v-overlay-container')),
      )
      expect(
        teleportadoParaOverlayContainer,
        'Tooltip não foi teleportado para .v-overlay-container no <body> — sem isso ele renderiza inline, sujeito à ordem de pintura normal do DOM em vez de um stacking context de overlay real.',
      ).toBe(true)

      const zIndexes = await page.evaluate(() => {
        const overlay = document.querySelector('.v-overlay--active.v-tooltip')
        const seletoresConcorrentes = ['.toast-container', '.req-connectivity-alert', '.req-route-feedback', '.req-skip-link']
        const concorrentes = seletoresConcorrentes
          .map((sel) => document.querySelector(sel))
          .filter(Boolean)
          .map((el) => Number(window.getComputedStyle(el).zIndex))
          .filter((z) => Number.isFinite(z))

        return {
          tooltip: overlay ? Number(window.getComputedStyle(overlay).zIndex) : null,
          concorrentes,
        }
      })

      expect(zIndexes.tooltip, 'z-index do tooltip ativo não encontrado no DOM').not.toBeNull()
      for (const zConcorrente of zIndexes.concorrentes) {
        expect(
          zIndexes.tooltip,
          `z-index do tooltip (${zIndexes.tooltip}) deveria ser maior que overlays concorrentes do app (${zIndexes.concorrentes.join(', ')})`,
        ).toBeGreaterThan(zConcorrente)
      }
    })
  }
})

test.describe('regressão: densidade de tabela inconsistente entre telas', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
  })

  test('todas as rotas com v-data-table/v-table usam a mesma densidade de fonte', async ({ page }) => {
    test.setTimeout(180_000)
    await loginDemo(page)

    const fontSizesPorRota = {}

    for (const rota of ROTAS_AUTENTICADAS) {
      await test.step(rota.path, async () => {
        await page.goto(rota.path)
        await expect(page.getByTestId(rota.testId)).toBeVisible({ timeout: 15000 })

        const tabela = page.locator('.v-data-table, .v-table').first()
        if ((await tabela.count()) === 0) return

        const fontSize = await tabela.evaluate((el) => window.getComputedStyle(el).fontSize)
        fontSizesPorRota[rota.path] = fontSize
      })
    }

    const rotasComTabela = Object.keys(fontSizesPorRota)
    expect(
      rotasComTabela.length,
      'Nenhuma rota com tabela foi encontrada — catálogo desatualizado ou seletor quebrado, cobertura inválida.',
    ).toBeGreaterThan(0)

    const valoresUnicos = new Set(Object.values(fontSizesPorRota))
    expect(
      valoresUnicos.size,
      `Tamanho de fonte de tabela inconsistente entre rotas: ${JSON.stringify(fontSizesPorRota, null, 2)}`,
    ).toBe(1)

    expect(
      [...valoresUnicos][0],
      'Tamanho de fonte de tabela não corresponde ao token --table-row-font-size (0.75rem = 12px).',
    ).toBe('12px')
  })
})
