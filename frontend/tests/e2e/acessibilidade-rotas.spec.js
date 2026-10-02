const fs = require('fs')
const path = require('path')
const { test, expect } = require('@playwright/test')
const AxeBuilder = require('@axe-core/playwright').default
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')

/**
 * Gate governado de acessibilidade para o catálogo completo de rotas.
 *
 * Estado alvo: WCAG 2.2 A/AA sem dívida automatizável aceita.
 *
 * Regras:
 * - nenhuma allowlist por rota/regra;
 * - qualquer violação retornada pelo axe para WCAG A/AA reprova o teste,
 *   independentemente da severidade atribuída pelo axe;
 * - resultados `incomplete` são publicados como evidência para revisão manual,
 *   porque não representam aprovação automática de conformidade;
 * - a página pública de login continua coberta também por
 *   `tests/e2e/accessibility-visual.spec.ts`.
 */

const TAGS_WCAG_AA = [
  'wcag2a',
  'wcag2aa',
  'wcag21a',
  'wcag21aa',
  'wcag22aa',
]

function parseCssColor(value) {
  const color = value.trim()
  const hexadecimal = color.match(/^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i)
  if (hexadecimal) {
    return hexadecimal.slice(1).map((channel) => Number.parseInt(channel, 16))
  }

  const rgb = color.match(/^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/i)
  if (rgb) return rgb.slice(1).map(Number)

  throw new Error(`Cor CSS não suportada no gate de contraste: ${value}`)
}

function luminanciaRelativa(rgb) {
  const [red, green, blue] = rgb.map((channel) => {
    const normalized = channel / 255
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4
  })
  return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)
}

function taxaContraste(foreground, background) {
  const foregroundLuminance = luminanciaRelativa(foreground)
  const backgroundLuminance = luminanciaRelativa(background)
  return (Math.max(foregroundLuminance, backgroundLuminance) + 0.05)
    / (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
}

function sobrepor(foreground, background, opacity) {
  return foreground.map((channel, index) => (
    (channel * opacity) + (background[index] * (1 - opacity))
  ))
}

async function medirContrasteAlertaServiceCase(page) {
  const amostra = await page.getByTestId('service-case-error').evaluate((alert) => {
    const content = alert.querySelector('.v-alert__content')
    const underlay = alert.querySelector('.v-alert__underlay')
    const application = alert.closest('.v-application') || document.documentElement
    const applicationStyle = getComputedStyle(application)
    return {
      foreground: getComputedStyle(content).color,
      overlay: getComputedStyle(underlay).backgroundColor,
      overlayOpacity: Number(getComputedStyle(underlay).opacity),
      backgroundCandidates: [
        applicationStyle.getPropertyValue('--bg-gradient-top'),
        applicationStyle.getPropertyValue('--bg'),
      ],
    }
  })

  const foreground = parseCssColor(amostra.foreground)
  const overlay = parseCssColor(amostra.overlay)
  const contrastes = amostra.backgroundCandidates.map((background) => {
    const effectiveBackground = sobrepor(
      overlay,
      parseCssColor(background),
      amostra.overlayOpacity,
    )
    return taxaContraste(foreground, effectiveBackground)
  })

  return {
    ...amostra,
    minimumContrast: Math.min(...contrastes),
  }
}

function carregarRotasCanonicas() {
  const arquivo = path.resolve(__dirname, '../../src/constants/rotasResponsivas.js')
  const source = fs.readFileSync(arquivo, 'utf8')
  const pattern = /\{\s*path:\s*'([^']+)',\s*testId:\s*'([^']+)',\s*titulo:\s*'([^']+)'\s*\}/g
  return [...source.matchAll(pattern)].map((match) => ({
    path: match[1] === '/estatisticas/:indicadorId'
      ? '/estatisticas/total-requisitos'
      : match[1] === '/service-cases/:caseId?'
        ? '/service-cases'
        : match[1],
    testId: match[2],
    public: match[1] === '/login',
  }))
}

function persistirJson(nome, valor) {
  const diretorio = path.resolve(process.cwd(), 'test-results/accessibility')
  fs.mkdirSync(diretorio, { recursive: true })
  fs.writeFileSync(path.join(diretorio, nome), `${JSON.stringify(valor, null, 2)}\n`, 'utf8')
}

const ROTAS_AUTENTICADAS = carregarRotasCanonicas().filter((item) => !item.public)

test.describe('acessibilidade: catálogo completo de rotas autenticadas', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
  })

  test('ServiceCase sem identificador expõe erro com contraste WCAG 2.2 AA', async ({ page }) => {
    await loginDemo(page)
    await page.goto('/service-cases')
    await expect(page.getByTestId('service-case-view')).toBeVisible()
    await expect(page.getByTestId('service-case-error')).toHaveCount(0)

    await page.getByTestId('service-case-load').click()

    const errorAlert = page.getByTestId('service-case-error')
    await expect(errorAlert).toBeVisible()
    await expect(errorAlert).toContainText('Informe o identificador do ServiceCase.')
    await expect(page).toHaveURL(/\/service-cases$/)

    const contrast = await medirContrasteAlertaServiceCase(page)
    expect(
      contrast.minimumContrast,
      `Contraste mínimo renderizado do alerta: ${JSON.stringify(contrast)}`,
    ).toBeGreaterThanOrEqual(4.5)
  })

  test('nenhuma rota autenticada possui violação automatizável WCAG 2.2 A/AA', async ({ page }) => {
    test.setTimeout(600_000)
    await loginDemo(page)

    const violacoesPorRota = {}
    const revisaoManualPorRota = {}

    for (const rota of ROTAS_AUTENTICADAS) {
      await test.step(rota.path, async () => {
        await page.goto(rota.path)
        await expect(page.getByTestId(rota.testId)).toBeVisible({ timeout: 15000 })

        const resultado = await new AxeBuilder({ page })
          .withTags(TAGS_WCAG_AA)
          .analyze()

        if (resultado.violations.length > 0) {
          violacoesPorRota[rota.path] = resultado.violations.map((item) => ({
            id: item.id,
            impact: item.impact,
            ajuda: item.help,
            tags: item.tags,
            ocorrencias: item.nodes.length,
            alvos: item.nodes.map((node) => node.target),
            html: item.nodes.map((node) => node.html),
          }))
        }

        if (resultado.incomplete.length > 0) {
          revisaoManualPorRota[rota.path] = resultado.incomplete.map((item) => ({
            id: item.id,
            impact: item.impact,
            ajuda: item.help,
            tags: item.tags,
            ocorrencias: item.nodes.length,
            alvos: item.nodes.map((node) => node.target),
          }))
        }
      })
    }

    const rotasComRevisaoManual = Object.keys(revisaoManualPorRota).length
    const resumo = {
      schema_version: 1,
      commit_sha: process.env.GITHUB_SHA || null,
      tags_wcag: TAGS_WCAG_AA,
      rotas_autenticadas: ROTAS_AUTENTICADAS.length,
      rotas_com_violacao: Object.keys(violacoesPorRota).length,
      rotas_com_revisao_manual_axe: rotasComRevisaoManual,
      resultado_automatizado: Object.keys(violacoesPorRota).length === 0 ? 'approved' : 'failed',
      conformidade_formal: 'pending_manual_audit',
    }

    persistirJson('wcag22-revisao-manual.json', revisaoManualPorRota)
    persistirJson('wcag22-violacoes.json', violacoesPorRota)
    persistirJson('wcag22-resumo.json', resumo)

    await test.info().attach('wcag22-revisao-manual.json', {
      body: JSON.stringify(revisaoManualPorRota, null, 2),
      contentType: 'application/json',
    })

    await test.info().attach('wcag22-violacoes.json', {
      body: JSON.stringify(violacoesPorRota, null, 2),
      contentType: 'application/json',
    })

    await test.info().attach('wcag22-resumo.json', {
      body: JSON.stringify(resumo, null, 2),
      contentType: 'application/json',
    })

    const paresCanonicos = ROTAS_AUTENTICADAS.map((item) => `${item.path}|${item.testId}`)
    expect(
      ROTAS_AUTENTICADAS.length,
      'Catálogo autenticado não pode regredir abaixo da baseline atual',
    ).toBeGreaterThanOrEqual(38)
    expect(
      new Set(paresCanonicos).size,
      'Catálogo autenticado deve permanecer sem duplicidades',
    ).toBe(paresCanonicos.length)
    expect(
      violacoesPorRota,
      `Violações automatizáveis WCAG 2.2 A/AA: ${JSON.stringify(violacoesPorRota, null, 2)}`,
    ).toEqual({})
  })
})
