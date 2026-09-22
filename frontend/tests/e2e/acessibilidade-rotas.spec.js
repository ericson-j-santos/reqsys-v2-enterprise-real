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

    expect(ROTAS_AUTENTICADAS.length, 'Catálogo autenticado deve conter exatamente 37 rotas').toBe(37)
    expect(
      violacoesPorRota,
      `Violações automatizáveis WCAG 2.2 A/AA: ${JSON.stringify(violacoesPorRota, null, 2)}`,
    ).toEqual({})
  })
})
