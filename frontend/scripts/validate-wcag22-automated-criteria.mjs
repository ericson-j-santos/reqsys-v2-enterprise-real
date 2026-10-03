#!/usr/bin/env node
/**
 * Valida, de forma fail-closed, a evidência produzida por
 * `tests/e2e/acessibilidade-teclado-foco.spec.js` para os critérios WCAG 2.2 AA
 * que dependem de estado de interação.
 *
 * O validador nunca aprova por ausência de dado: arquivo faltando, esquema
 * divergente, critério ausente, lista de ocorrências não vazia ou construção de
 * allowlist no próprio teste reprovam a execução.
 *
 * Uso: `npm run validate:wcag22-automated-criteria`
 */
import fs from 'node:fs'
import path from 'node:path'

export const CRITERIOS_AUTOMATIZADOS = ['keyboard_navigation', 'focus_visibility_and_not_obscured']

const LISTAS_QUE_DEVEM_ESTAR_VAZIAS = {
  keyboard_navigation: ['armadilhas'],
  focus_visibility_and_not_obscured: [
    'sem_indicador_de_foco',
    'foco_encoberto',
    'foco_fora_do_viewport',
    'nao_avaliaveis',
  ],
}

/** Construções que transformariam o gate em aprovação seletiva. */
const CONSTRUCOES_PROIBIDAS = [
  ['ALLOWLIST', 'allowlist técnica'],
  ['EXCECOES_ACEITAS', 'lista de exceções aceitas'],
  ['ROTAS_IGNORADAS', 'lista de rotas ignoradas'],
  ['test.skip(', 'teste desativado'],
  ['test.fixme(', 'teste marcado como fixme'],
]

export function validarEvidencia(evidencia, fonteDoTeste) {
  const erros = []

  if (!evidencia || typeof evidencia !== 'object') {
    return { status: 'failed', erros: ['Evidência ausente ou inválida.'] }
  }
  if (evidencia.schema_version !== 1) {
    erros.push(`Versão de esquema inesperada: ${evidencia.schema_version}`)
  }
  if (!Number.isInteger(evidencia.rotas_autenticadas) || evidencia.rotas_autenticadas <= 0) {
    erros.push(`Número de rotas autenticadas inválido: ${evidencia.rotas_autenticadas}`)
  }
  if (!Number.isInteger(evidencia.paradas_de_tabulacao_avaliadas) || evidencia.paradas_de_tabulacao_avaliadas <= 0) {
    erros.push(
      `Nenhuma parada de tabulação foi avaliada: ${evidencia.paradas_de_tabulacao_avaliadas}. ` +
        'Execução vazia não pode ser lida como aprovação.',
    )
  }

  const criterios = evidencia.criterios || {}
  for (const id of CRITERIOS_AUTOMATIZADOS) {
    const criterio = criterios[id]
    if (!criterio) {
      erros.push(`Critério ausente na evidência: ${id}`)
      continue
    }
    if (criterio.status !== 'approved') {
      erros.push(`Critério não aprovado: ${id} (status=${criterio.status})`)
    }
    for (const lista of LISTAS_QUE_DEVEM_ESTAR_VAZIAS[id]) {
      const valor = criterio.evidencia?.[lista]
      if (!Array.isArray(valor)) {
        erros.push(`Lista de ocorrências ausente em ${id}: ${lista}`)
      } else if (valor.length > 0) {
        erros.push(`Ocorrências não tratadas em ${id}.${lista}: ${valor.length}`)
      }
    }
  }

  const login = criterios.keyboard_navigation?.evidencia?.login_somente_teclado
  if (!login?.alcancado_por_tabulacao || !login?.autenticado_sem_mouse) {
    erros.push('Fluxo de entrada não foi comprovado apenas com teclado (SC 2.1.1).')
  }

  if (typeof fonteDoTeste === 'string') {
    for (const [trecho, descricao] of CONSTRUCOES_PROIBIDAS) {
      if (fonteDoTeste.includes(trecho)) {
        erros.push(`Gate inválido: detectada ${descricao} (${trecho})`)
      }
    }
  } else {
    erros.push('Código do gate não pôde ser lido para verificação de allowlist.')
  }

  return { status: erros.length === 0 ? 'approved' : 'failed', erros }
}

function principal() {
  const raiz = process.cwd()
  const diretorio = path.join(raiz, 'test-results', 'accessibility')
  const arquivoEvidencia = path.join(diretorio, 'wcag22-criterios-automatizados.json')
  const arquivoTeste = path.join(raiz, 'tests', 'e2e', 'acessibilidade-teclado-foco.spec.js')

  let evidencia = null
  if (fs.existsSync(arquivoEvidencia)) {
    try {
      evidencia = JSON.parse(fs.readFileSync(arquivoEvidencia, 'utf8'))
    } catch (erro) {
      console.error(JSON.stringify({ status: 'failed', erros: [`Evidência ilegível: ${erro.message}`] }, null, 2))
      process.exitCode = 2
      return
    }
  } else {
    console.error(
      JSON.stringify({ status: 'failed', erros: [`Evidência ausente: ${arquivoEvidencia}`] }, null, 2),
    )
    process.exitCode = 2
    return
  }

  const fonteDoTeste = fs.existsSync(arquivoTeste) ? fs.readFileSync(arquivoTeste, 'utf8') : null
  const resultado = validarEvidencia(evidencia, fonteDoTeste)

  const saida = {
    status: resultado.status,
    criterios_automatizados: CRITERIOS_AUTOMATIZADOS,
    rotas_autenticadas: evidencia.rotas_autenticadas ?? null,
    paradas_de_tabulacao_avaliadas: evidencia.paradas_de_tabulacao_avaliadas ?? null,
    erros: resultado.erros,
  }

  fs.mkdirSync(diretorio, { recursive: true })
  fs.writeFileSync(
    path.join(diretorio, 'wcag22-criterios-automatizados-validacao.json'),
    `${JSON.stringify(saida, null, 2)}\n`,
    'utf8',
  )

  console.log(JSON.stringify(saida, null, 2))

  if (process.env.GITHUB_STEP_SUMMARY) {
    fs.appendFileSync(
      process.env.GITHUB_STEP_SUMMARY,
      `\n## WCAG 2.2 AA — critérios automatizados de teclado e foco\n\n` +
        `- Estado: **${saida.status}**\n` +
        `- Rotas autenticadas: **${saida.rotas_autenticadas}**\n` +
        `- Paradas de tabulação avaliadas: **${saida.paradas_de_tabulacao_avaliadas}**\n` +
        `- Erros: **${saida.erros.length}**\n`,
    )
  }

  if (resultado.status !== 'approved') process.exitCode = 2
}

if (import.meta.url === `file://${process.argv[1]}`) {
  principal()
}
