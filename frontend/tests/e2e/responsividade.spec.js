const fs = require('fs')
const path = require('path')
const { test, expect } = require('@playwright/test')
const {
  mockResponsiveApis,
  loginDemo,
} = require('./helpers/responsiveMocks')

function carregarRotasCanonicas() {
  const arquivo = path.resolve(__dirname, '../../src/constants/rotasResponsivas.js')
  const source = fs.readFileSync(arquivo, 'utf8')
  const pattern = /\{\s*path:\s*'([^']+)',\s*testId:\s*'([^']+)',\s*titulo:\s*'([^']+)'\s*\}/g
  const rotas = [...source.matchAll(pattern)].map((match) => ({
    path: match[1] === '/estatisticas/:indicadorId' ? '/estatisticas/total-requisitos' : match[1],
    canonicalPath: match[1],
    testId: match[2],
    titulo: match[3],
    public: match[1] === '/login',
  }))

  if (!rotas.length) {
    throw new Error('Catálogo canônico de responsividade não pôde ser carregado.')
  }

  return rotas
}

const ROTAS_RESPONSIVAS = carregarRotasCanonicas()
const ROTAS_AUTENTICADAS = ROTAS_RESPONSIVAS.filter((item) => !item.public)
const ROTAS_PARETO = ROTAS_AUTENTICADAS.filter((item) => [
  '/',
  '/pipeline',
  '/relatorios',
  '/hub-lowcode',
  '/painel-integracao',
  '/govbi-ia',
  '/monitoramento-operacional',
  '/admin/teams-recipient-policies',
  '/admin/operational-deploy',
].includes(item.canonicalPath))

const VIEWPORTS_COMPLETOS = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'desktop', width: 1366, height: 768 },
]

const VIEWPORTS_PARETO = [
  { name: 'mobile-compacto', width: 320, height: 568 },
  { name: 'tablet', width: 768, height: 1024 },
]

async function horizontalOverflowEvidence(page) {
  return page.evaluate(() => {
    const descreverElemento = (element, containerRect) => {
      const rect = element.getBoundingClientRect()
      const style = window.getComputedStyle(element)
      const parent = element.parentElement
      const texto = String(element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 80)
      const classes = typeof element.className === 'string'
        ? element.className.split(/\s+/).filter(Boolean).slice(0, 5).join('.')
        : ''
      const classesPai = parent && typeof parent.className === 'string'
        ? parent.className.split(/\s+/).filter(Boolean).slice(0, 5).join('.')
        : ''

      return {
        tag: element.tagName.toLowerCase(),
        id: element.id || null,
        testId: element.getAttribute('data-testid'),
        classes: classes || null,
        pai: parent ? `${parent.tagName.toLowerCase()}${classesPai ? `.${classesPai}` : ''}` : null,
        texto: texto || null,
        left: Math.floor(rect.left),
        right: Math.ceil(rect.right),
        width: Math.ceil(rect.width),
        scrollWidth: Math.ceil(element.scrollWidth),
        clientWidth: Math.ceil(element.clientWidth),
        excessoDireita: Math.max(0, Math.ceil(rect.right - containerRect.right)),
        margemDireita: style.marginRight,
        paddingDireita: style.paddingRight,
        position: style.position,
        transform: style.transform === 'none' ? null : style.transform,
        overflowX: style.overflowX,
      }
    }

    const overflowEstaContido = (child, target, targetRect) => {
      let ancestor = child.parentElement
      while (ancestor && ancestor !== target) {
        const style = window.getComputedStyle(ancestor)
        const overflowX = style.overflowX
        if (['auto', 'scroll', 'hidden', 'clip'].includes(overflowX)) {
          const rect = ancestor.getBoundingClientRect()
          const dentroDoTarget = rect.left >= targetRect.left - 2 && rect.right <= targetRect.right + 2
          if (dentroDoTarget) return true
        }
        ancestor = ancestor.parentElement
      }
      return false
    }

    const targets = [
      ['documento', document.documentElement],
      ['body', document.body],
      ['conteudo-principal', document.querySelector('.req-main')],
      ['barra-superior', document.querySelector('.req-appbar .v-toolbar__content')],
    ].filter(([, element]) => element)

    return targets
      .map(([name, element]) => {
        const item = {
          name,
          scrollWidth: Math.ceil(element.scrollWidth),
          clientWidth: Math.ceil(element.clientWidth),
        }
        if (item.scrollWidth <= item.clientWidth + 2) return item

        const containerRect = element.getBoundingClientRect()
        item.ofensoresDireita = [...element.querySelectorAll('*')]
          .filter((child) => {
            const rect = child.getBoundingClientRect()
            return rect.width > 0 &&
              rect.right > containerRect.right + 2 &&
              !overflowEstaContido(child, element, containerRect)
          })
          .map((child) => descreverElemento(child, containerRect))
          .sort((a, b) => b.excessoDireita - a.excessoDireita)
          .slice(0, 12)

        return item
      })
      .filter((item) => item.scrollWidth > item.clientWidth + 2)
  })
}

async function expectSemOverflowHorizontal(page) {
  const evidence = await horizontalOverflowEvidence(page)
  expect(evidence, `Overflow horizontal detectado: ${JSON.stringify(evidence)}`).toEqual([])
}

test.describe(`responsividade padrão ouro — ${ROTAS_RESPONSIVAS.length} rotas canônicas`, () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
  })

  test('catálogo canônico permanece íntegro e sem duplicidades', () => {
    const pares = ROTAS_RESPONSIVAS.map((item) => `${item.canonicalPath}|${item.testId}`)
    expect(ROTAS_RESPONSIVAS.length).toBeGreaterThanOrEqual(36)
    expect(new Set(pares).size).toBe(pares.length)
  })

  for (const viewport of VIEWPORTS_COMPLETOS) {
    test(`catálogo completo sem overflow horizontal em ${viewport.name}`, async ({ page }) => {
      test.setTimeout(120_000)
      await page.setViewportSize({ width: viewport.width, height: viewport.height })

      await page.goto('/login')
      await expect(page.getByTestId('route-login')).toBeVisible()
      await expectSemOverflowHorizontal(page)

      await loginDemo(page)

      for (const rota of ROTAS_AUTENTICADAS) {
        await test.step(`${viewport.name}: ${rota.path}`, async () => {
          await page.goto(rota.path)
          await expect(page.getByTestId(rota.testId)).toBeVisible({ timeout: 15000 })
          await expectSemOverflowHorizontal(page)
        })
      }
    })
  }

  for (const viewport of VIEWPORTS_PARETO) {
    test(`rotas de maior densidade sem overflow em ${viewport.name}`, async ({ page }) => {
      test.setTimeout(90_000)
      await page.setViewportSize({ width: viewport.width, height: viewport.height })
      await loginDemo(page)

      for (const rota of ROTAS_PARETO) {
        await test.step(`${viewport.name}: ${rota.path}`, async () => {
          await page.goto(rota.path)
          await expect(page.getByTestId(rota.testId)).toBeVisible({ timeout: 15000 })
          await expectSemOverflowHorizontal(page)
        })
      }
    })
  }

  test('menu mobile abre e navega sem deslocar conteúdo em 320px', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 568 })
    await loginDemo(page)

    await page.locator('button[aria-label="Abrir menu de navegação"]').click()
    await page.getByTestId('nav-tema-requisitos').click()
    const menuLink = page.getByTestId('nav-subgrupo-entrada').getByTestId('nav-item-requisitos')
    await expect(menuLink).toBeVisible()
    await menuLink.click()
    await expect(page).toHaveURL(/\/requisitos$/)
    await expect(page.getByTestId('route-requisitos')).toBeVisible()
    await expectSemOverflowHorizontal(page)
  })

  test('dashboard preserva cards críticos e barra superior em 320px', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 568 })
    await loginDemo(page)

    await expect(page.getByTestId('metric-card-minhas-demandas')).toBeVisible()
    await expect(page.getByTestId('dashboard-info-card')).toBeVisible()
    await expect(page.locator('.req-appbar')).toBeVisible()
    await expectSemOverflowHorizontal(page)
  })
})
