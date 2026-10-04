import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

const VALIDADOR = fs.readFileSync(
  new URL('./validate-wcag22-evidence.mjs', import.meta.url),
  'utf8',
)

const TAGS_WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

function entradaCatalogo(rota, indice, formato = 'canonico') {
  const testId = `route-${indice}`
  const titulo = `Rota ${indice}`
  if (formato === 'ordem-alterada') {
    return `{ testId: '${testId}', path: '${rota}', titulo: '${titulo}' }`
  }
  if (formato === 'aspas-duplas') {
    return `{ path: "${rota}", testId: "${testId}", titulo: "${titulo}" }`
  }
  return `{ path: '${rota}', testId: '${testId}', titulo: '${titulo}' }`
}

function criarFixture(formatoPrimeiraRotaAutenticada = 'canonico') {
  const raiz = fs.mkdtempSync(path.join(os.tmpdir(), 'wcag22-evidence-parser-'))
  fs.mkdirSync(path.join(raiz, 'scripts'), { recursive: true })
  fs.mkdirSync(path.join(raiz, 'src/constants'), { recursive: true })
  fs.mkdirSync(path.join(raiz, 'tests/e2e'), { recursive: true })
  fs.mkdirSync(path.join(raiz, 'test-results/accessibility'), { recursive: true })

  fs.writeFileSync(path.join(raiz, 'scripts/validate-wcag22-evidence.mjs'), VALIDADOR)
  fs.writeFileSync(
    path.join(raiz, 'tests/e2e/acessibilidade-rotas.spec.js'),
    "test('catálogo completo', () => {})\n",
  )

  const rotas = ['/login', ...Array.from({ length: 38 }, (_, indice) => `/rota-${indice + 1}`)]
  const entradas = rotas.map((rota, indice) =>
    entradaCatalogo(rota, indice, indice === 1 ? formatoPrimeiraRotaAutenticada : 'canonico'),
  )
  fs.writeFileSync(
    path.join(raiz, 'src/constants/rotasResponsivas.js'),
    `export const ROTAS_RESPONSIVAS = [\n  ${entradas.join(',\n  ')},\n]\n`,
  )

  const diretorioEvidencia = path.join(raiz, 'test-results/accessibility')
  fs.writeFileSync(
    path.join(diretorioEvidencia, 'wcag22-resumo.json'),
    JSON.stringify({
      schema_version: 1,
      rotas_autenticadas: 38,
      resultado_automatizado: 'approved',
      conformidade_formal: 'pending_manual_audit',
      tags_wcag: TAGS_WCAG,
    }),
  )
  fs.writeFileSync(path.join(diretorioEvidencia, 'wcag22-violacoes.json'), '{}')
  fs.writeFileSync(path.join(diretorioEvidencia, 'wcag22-revisao-manual.json'), '{}')

  return raiz
}

function executarValidador(raiz) {
  return spawnSync(process.execPath, ['scripts/validate-wcag22-evidence.mjs'], {
    cwd: raiz,
    encoding: 'utf8',
  })
}

function removerFixture(raiz) {
  assert.match(raiz, /wcag22-evidence-parser-/)
  fs.rmSync(raiz, { recursive: true, force: true })
}

test('deriva 38 rotas autenticadas do catálogo canônico atual', (t) => {
  const raiz = criarFixture()
  t.after(() => removerFixture(raiz))

  const resultado = executarValidador(raiz)

  assert.equal(resultado.status, 0, resultado.stderr || resultado.stdout)
  const evidencia = JSON.parse(
    fs.readFileSync(
      path.join(raiz, 'test-results/accessibility/wcag22-validacao-evidencia.json'),
      'utf8',
    ),
  )
  assert.equal(evidencia.rotas_autenticadas, 38)
  assert.equal(evidencia.status, 'approved')
})

test('falha fechado quando a ordem dos campos diverge do formato canônico', (t) => {
  const raiz = criarFixture('ordem-alterada')
  t.after(() => removerFixture(raiz))

  const resultado = executarValidador(raiz)

  assert.notEqual(resultado.status, 0)
  assert.match(resultado.stderr, /Catálogo canônico incompleto: 38 rotas encontradas/)
})

test('falha fechado quando o catálogo troca o formato de aspas', (t) => {
  const raiz = criarFixture('aspas-duplas')
  t.after(() => removerFixture(raiz))

  const resultado = executarValidador(raiz)

  assert.notEqual(resultado.status, 0)
  assert.match(resultado.stderr, /Catálogo canônico incompleto: 38 rotas encontradas/)
})
