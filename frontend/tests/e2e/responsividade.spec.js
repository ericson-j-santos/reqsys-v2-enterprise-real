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

const PERMISSOES_ADMIN_RESPONSIVIDADE = [
  'teams-recipient-policies:admin',
  'operational-deploy:admin',
  'security-sessions:admin',
  'ocr-review:admin',
]

async function elevarPermissoesAdministrativas(page) {
  await page.evaluate((permissoesExtras) => {
    const raw = localStorage.getItem('reqsys_usuario')
    if (!raw) throw new Error('Sessão demo não encontrada para teste responsivo.')
    const usuario = JSON.parse(raw)
    usuario.permissoes = [...new Set([...(usuario.permissoes || []), ...permissoesExtras])]
    localStorage.setItem('reqsys_usuario', JSON.stringify(usuario))
  }, PERMISSOES_ADMIN_RESPONSIVIDADE)
  await page.reload()
}

async function horizontalOverflowEvidence(page) {
  return page.evaluate(() => {
    const targets = [
      ['documento', document.documentElement],
      ['body', document.body],
      ['conteudo-principal', document.querySelector('.req-main')],
      ['barra-superior', document.querySelector('.req-appbar .v-toolbar__content')],
    ].filter(([, element]) => element)

    return targets
      .map(([name, element]) => ({
        name,
        scrollWidth: Math.ceil(element.scrollWidth),
        clientWidth: Math.ceil(element.clientWidth),
      }))
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
      await elevarPermissoesAdministrativas(page)

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
      await elevarPermissoesAdministrativas(page)

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
