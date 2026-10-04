const fs = require('fs')
const path = require('path')
const { test, expect } = require('@playwright/test')
const { mockResponsiveApis } = require('./helpers/responsiveMocks')

/**
 * Gate governado para os critérios WCAG 2.2 AA que dependem de estado de
 * interação e, por isso, não são cobertos pelo axe-core em
 * `tests/e2e/acessibilidade-rotas.spec.js`:
 *
 * - `keyboard_navigation`               — SC 2.1.1 (Teclado) e SC 2.1.2 (Sem armadilha).
 * - `focus_visibility_and_not_obscured` — SC 2.4.7 (Foco visível) e SC 2.4.11 (Foco não encoberto).
 *
 * Regras:
 * - nenhuma allowlist por rota, seletor ou elemento;
 * - qualquer parada de tabulação sem diferença visual entre focado e não
 *   focado reprova o teste;
 * - a evidência é gravada por execução e validada por
 *   `scripts/validate-wcag22-automated-criteria.mjs`, que falha fechado;
 * - os critérios que exigem leitor de tela real e avaliação cognitiva
 *   permanecem fora deste gate e continuam registrados como pendência humana
 *   em `governance/accessibility/wcag22-aa-manual-audit.json`.
 */

const MAX_PARADAS = 80
/** Acomodação de transições CSS disparadas pelo foco (ex.: skip link). */
const ESPERA_TRANSICAO_MS = 220
const DIRETORIO_EVIDENCIA = 'test-results/accessibility'
const ARQUIVO_EVIDENCIA = 'wcag22-criterios-automatizados.json'

function carregarRotasCanonicas() {
  const arquivo = path.resolve(__dirname, '../../src/constants/rotasResponsivas.js')
  const source = fs.readFileSync(arquivo, 'utf8')
  const pattern = /\{\s*path:\s*'([^']+)',\s*testId:\s*'([^']+)',\s*titulo:\s*'([^']+)'\s*\}/g
  const rotas = [...source.matchAll(pattern)].map((match) => ({
    path: match[1] === '/estatisticas/:indicadorId' ? '/estatisticas/total-requisitos' : match[1],
    testId: match[2],
    public: match[1] === '/login',
  }))

  if (!rotas.length) {
    throw new Error('Catálogo canônico de rotas não pôde ser carregado.')
  }

  return rotas
}

const ROTAS_AUTENTICADAS = carregarRotasCanonicas().filter((item) => !item.public)

/**
 * Auxiliares instalados na página por `addInitScript`; ficam disponíveis em
 * `window.__a11y` após cada navegação, inclusive recarregamentos.
 */
function instalarAuxiliares() {
  const propriedades = (estilo) => [
    estilo.outlineStyle,
    estilo.outlineWidth,
    estilo.outlineColor,
    estilo.outlineOffset,
    estilo.boxShadow,
    estilo.border,
    estilo.backgroundColor,
    estilo.backgroundImage,
    estilo.color,
    estilo.opacity,
    estilo.filter,
    estilo.textDecorationLine,
  ].join('~')

  window.__a11y = {
    /**
     * Serializa a aparência do elemento e de seus descendentes diretos,
     * incluindo pseudo-elementos. Cobre indicadores desenhados por outline,
     * sombra, borda, fundo, opacidade ou camada de sobreposição — este último
     * é o padrão usado pelo Vuetify.
     */
    aparencia(elemento) {
      const nos = [elemento, ...Array.from(elemento.querySelectorAll('*')).slice(0, 16)]
      const proprio = nos.map((no) => propriedades(getComputedStyle(no))).join('|')
      const antes = propriedades(getComputedStyle(elemento, '::before'))
      const depois = propriedades(getComputedStyle(elemento, '::after'))
      return `${proprio}||${antes}||${depois}`
    },

    /** Caminho estrutural estável, reproduzível enquanto o nó existir no DOM. */
    caminho(elemento) {
      const partes = []
      let atual = elemento
      while (atual && atual !== document.documentElement) {
        const pai = atual.parentElement
        if (!pai) break
        const indice = Array.prototype.indexOf.call(pai.children, atual)
        partes.unshift(`${atual.tagName.toLowerCase()}:nth-child(${indice + 1})`)
        atual = pai
      }
      return partes.join(' > ')
    },

    /**
     * SC 2.4.11 trata do foco encoberto por conteúdo do autor — tipicamente
     * barras fixas ou aderentes sobrepostas ao elemento focado. Sobreposições
     * internas do próprio widget (por exemplo o overlay de um campo Vuetify)
     * não encobrem o foco e não são contabilizadas.
     */
    encoberto(elemento) {
      const retangulo = elemento.getBoundingClientRect()
      if (retangulo.width === 0 || retangulo.height === 0) return false

      const amostras = [
        [retangulo.left + retangulo.width / 2, retangulo.top + retangulo.height / 2],
        [retangulo.left + 2, retangulo.top + 2],
        [retangulo.right - 2, retangulo.top + 2],
        [retangulo.left + 2, retangulo.bottom - 2],
        [retangulo.right - 2, retangulo.bottom - 2],
      ].filter(([x, y]) => x >= 0 && y >= 0 && x <= window.innerWidth && y <= window.innerHeight)

      if (amostras.length === 0) return false

      const sobBarraFixa = (no) => {
        let atual = no
        while (atual && atual !== document.documentElement) {
          const posicao = getComputedStyle(atual).position
          if (posicao === 'fixed' || posicao === 'sticky') return true
          atual = atual.parentElement
        }
        return false
      }

      let pontosLivres = 0
      for (const [x, y] of amostras) {
        const noTopo = document.elementFromPoint(x, y)
        if (!noTopo) continue
        if (noTopo === elemento || elemento.contains(noTopo) || noTopo.contains(elemento)) {
          pontosLivres += 1
          continue
        }
        if (!sobBarraFixa(noTopo)) pontosLivres += 1
      }

      return pontosLivres === 0
    },
  }
}

function lerParadaFocada(page) {
  return page.evaluate(() => {
    const aux = window.__a11y
    const elemento = document.activeElement
    if (!elemento || elemento === document.body || elemento === document.documentElement) {
      return null
    }

    elemento.scrollIntoView({ block: 'center', inline: 'center' })
    const retangulo = elemento.getBoundingClientRect()

    return {
      caminho: aux.caminho(elemento),
      tag: elemento.tagName.toLowerCase(),
      papel: elemento.getAttribute('role') || '',
      area: { largura: Math.round(retangulo.width), altura: Math.round(retangulo.height) },
      dentro_do_viewport:
        retangulo.top < window.innerHeight &&
        retangulo.bottom > 0 &&
        retangulo.left < window.innerWidth &&
        retangulo.right > 0,
      encoberto: aux.encoberto(elemento),
      aparencia_focada: aux.aparencia(elemento),
    }
  })
}

/**
 * Lê a aparência sem foco de um elemento já visitado, depois que a tabulação
 * avançou: o elemento continua no mesmo estado de DOM, agora sem foco.
 * Retorna `null` se o elemento saiu do DOM e `'focus_within'` se ele ainda
 * contém o foco corrente.
 */
function lerAparenciaSemFoco(page, seletor) {
  return page.evaluate((caminho) => {
    const elemento = document.querySelector(caminho)
    if (!elemento) return null
    if (elemento.contains(document.activeElement)) return 'focus_within'
    return window.__a11y.aparencia(elemento)
  }, seletor)
}

/**
 * Percorre a ordem de tabulação até fechar o ciclo, provando ausência de
 * armadilha (SC 2.1.2), e coleta a aparência focada e não focada de cada
 * parada (SC 2.4.7 / 2.4.11).
 */
async function percorrerTabulacao(page) {
  const paradas = []
  const vistos = new Set()
  let cicloFechado = false
  let retornosAoDocumento = 0
  let anterior = null

  const registrarAparenciaSemFoco = async (parada) => {
    if (!parada) return
    // `focus_within` ocorre em widgets compostos, cujo contêiner continua
    // contendo o foco depois que a tabulação avançou para um filho. A leitura
    // é adiada e repetida até o foco deixar toda a subárvore.
    if (parada.aparencia_sem_foco !== undefined && parada.aparencia_sem_foco !== 'focus_within') return
    parada.aparencia_sem_foco = await lerAparenciaSemFoco(page, parada.caminho)
  }

  const resolverPendentes = async () => {
    for (const parada of paradas) {
      if (parada.aparencia_sem_foco === 'focus_within') {
        await registrarAparenciaSemFoco(parada)
      }
    }
  }

  for (let i = 0; i < MAX_PARADAS; i += 1) {
    await page.keyboard.press('Tab')
    await page.waitForTimeout(ESPERA_TRANSICAO_MS)
    const parada = await lerParadaFocada(page)

    await registrarAparenciaSemFoco(anterior)
    await resolverPendentes()
    anterior = null

    if (!parada) {
      retornosAoDocumento += 1
      // O foco voltou ao documento: o ciclo fechou sem prender o usuário.
      if (paradas.length > 0) {
        cicloFechado = true
        break
      }
      if (retornosAoDocumento > 2) break
      continue
    }

    if (vistos.has(parada.caminho)) {
      cicloFechado = true
      break
    }

    vistos.add(parada.caminho)
    paradas.push(parada)
    anterior = parada
  }

  // Retira o foco do documento para medir a última parada e qualquer widget
  // composto cujo contêiner ainda retinha o foco.
  await page.evaluate(() => document.activeElement && document.activeElement.blur())
  await page.waitForTimeout(ESPERA_TRANSICAO_MS)
  await registrarAparenciaSemFoco(anterior)
  await resolverPendentes()

  return { paradas, cicloFechado }
}

function persistirEvidencia(conteudo) {
  const diretorio = path.resolve(process.cwd(), DIRETORIO_EVIDENCIA)
  fs.mkdirSync(diretorio, { recursive: true })
  fs.writeFileSync(
    path.join(diretorio, ARQUIVO_EVIDENCIA),
    `${JSON.stringify(conteudo, null, 2)}\n`,
    'utf8',
  )
}

test.describe('acessibilidade: teclado e foco visível nas rotas autenticadas', () => {
  test('critérios WCAG 2.2 AA dependentes de interação são aprovados sem exceção', async ({ page }) => {
    test.setTimeout(1_800_000)
    await page.addInitScript(instalarAuxiliares)
    await mockResponsiveApis(page)

    // SC 2.1.1 — o fluxo crítico de entrada precisa ser concluível só com teclado.
    await page.goto('/login')
    const entrar = page.getByRole('button', { name: /entrar \(demo\)/i })
    await expect(entrar).toBeVisible({ timeout: 15000 })

    let alcancouEntrar = false
    for (let i = 0; i < MAX_PARADAS && !alcancouEntrar; i += 1) {
      await page.keyboard.press('Tab')
      alcancouEntrar = await entrar.evaluate((elemento) => elemento === document.activeElement)
    }
    expect(alcancouEntrar, 'Botão de entrada não foi alcançado pela tabulação na rota /login').toBe(true)
    await page.keyboard.press('Enter')
    await page.waitForURL('**/')

    const loginSomenteTeclado = {
      rota: '/login',
      alcancado_por_tabulacao: alcancouEntrar,
      autenticado_sem_mouse: true,
    }

    const rotasAvaliadas = {}
    const armadilhas = []
    const foraDoViewport = []
    const encobertos = []
    const semIndicadorDeFoco = []
    const naoAvaliaveis = []

    for (const rota of ROTAS_AUTENTICADAS) {
      await test.step(rota.path, async () => {
        await page.goto(rota.path)
        await expect(page.getByTestId(rota.testId)).toBeVisible({ timeout: 15000 })

        const { paradas, cicloFechado } = await percorrerTabulacao(page)

        if (paradas.length === 0) {
          armadilhas.push({ rota: rota.path, motivo: 'nenhuma_parada_alcancada' })
        }
        if (!cicloFechado) {
          armadilhas.push({ rota: rota.path, motivo: 'ciclo_de_tabulacao_nao_fechou' })
        }

        for (const parada of paradas) {
          const identificacao = { rota: rota.path, caminho: parada.caminho, tag: parada.tag }

          if (!parada.dentro_do_viewport) foraDoViewport.push(identificacao)
          if (parada.encoberto) encobertos.push(identificacao)

          if (parada.aparencia_sem_foco === null || parada.aparencia_sem_foco === 'focus_within') {
            naoAvaliaveis.push({
              ...identificacao,
              motivo: parada.aparencia_sem_foco === null ? 'removido_do_dom' : 'foco_interno_persistente',
            })
            continue
          }
          if (parada.aparencia_sem_foco === parada.aparencia_focada) {
            semIndicadorDeFoco.push(identificacao)
          }
        }

        rotasAvaliadas[rota.path] = {
          paradas_de_tabulacao: paradas.length,
          ciclo_fechado: cicloFechado,
        }
      })
    }

    const totalParadas = Object.values(rotasAvaliadas).reduce(
      (acumulado, item) => acumulado + item.paradas_de_tabulacao,
      0,
    )

    const evidencia = {
      schema_version: 1,
      padrao: 'WCAG 2.2 AA',
      rotas_autenticadas: ROTAS_AUTENTICADAS.length,
      paradas_de_tabulacao_avaliadas: totalParadas,
      criterios: {
        keyboard_navigation: {
          criterios_wcag: ['2.1.1', '2.1.2'],
          status: armadilhas.length === 0 && totalParadas > 0 ? 'approved' : 'failed',
          evidencia: {
            login_somente_teclado: loginSomenteTeclado,
            rotas: rotasAvaliadas,
            armadilhas,
          },
        },
        focus_visibility_and_not_obscured: {
          criterios_wcag: ['2.4.7', '2.4.11'],
          status:
            semIndicadorDeFoco.length === 0 &&
            encobertos.length === 0 &&
            foraDoViewport.length === 0 &&
            naoAvaliaveis.length === 0
              ? 'approved'
              : 'failed',
          evidencia: {
            paradas_avaliadas: totalParadas,
            sem_indicador_de_foco: semIndicadorDeFoco,
            foco_encoberto: encobertos,
            foco_fora_do_viewport: foraDoViewport,
            nao_avaliaveis: naoAvaliaveis,
          },
        },
      },
      criterios_fora_deste_gate: ['screen_reader_critical_flows', 'accessible_authentication'],
    }

    persistirEvidencia(evidencia)

    expect(armadilhas, JSON.stringify(armadilhas, null, 2)).toEqual([])
    expect(totalParadas).toBeGreaterThan(0)
    expect(semIndicadorDeFoco, JSON.stringify(semIndicadorDeFoco.slice(0, 20), null, 2)).toEqual([])
    expect(encobertos, JSON.stringify(encobertos.slice(0, 20), null, 2)).toEqual([])
    expect(foraDoViewport, JSON.stringify(foraDoViewport.slice(0, 20), null, 2)).toEqual([])
    expect(naoAvaliaveis, JSON.stringify(naoAvaliaveis.slice(0, 20), null, 2)).toEqual([])
  })
})
