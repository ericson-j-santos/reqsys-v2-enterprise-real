import test from 'node:test'
import assert from 'node:assert/strict'

import { validarEvidencia, CRITERIOS_AUTOMATIZADOS } from './validate-wcag22-automated-criteria.mjs'

const FONTE_LIMPA = 'test.describe("gate", () => { /* sem allowlist */ })'

function evidenciaAprovada(sobrescritas = {}) {
  return {
    schema_version: 1,
    padrao: 'WCAG 2.2 AA',
    rotas_autenticadas: 37,
    paradas_de_tabulacao_avaliadas: 381,
    criterios: {
      keyboard_navigation: {
        criterios_wcag: ['2.1.1', '2.1.2'],
        status: 'approved',
        evidencia: {
          login_somente_teclado: {
            rota: '/login',
            alcancado_por_tabulacao: true,
            autenticado_sem_mouse: true,
          },
          rotas: { '/': { paradas_de_tabulacao: 24, ciclo_fechado: true } },
          armadilhas: [],
        },
      },
      focus_visibility_and_not_obscured: {
        criterios_wcag: ['2.4.7', '2.4.11'],
        status: 'approved',
        evidencia: {
          paradas_avaliadas: 381,
          sem_indicador_de_foco: [],
          foco_encoberto: [],
          foco_fora_do_viewport: [],
          nao_avaliaveis: [],
        },
      },
    },
    ...sobrescritas,
  }
}

test('aprova evidência completa e sem ocorrências', () => {
  const resultado = validarEvidencia(evidenciaAprovada(), FONTE_LIMPA)
  assert.equal(resultado.status, 'approved')
  assert.deepEqual(resultado.erros, [])
})

test('expõe exatamente os critérios cobertos pelo gate automatizado', () => {
  assert.deepEqual(CRITERIOS_AUTOMATIZADOS, ['keyboard_navigation', 'focus_visibility_and_not_obscured'])
})

test('reprova quando há parada de tabulação sem indicador de foco', () => {
  const evidencia = evidenciaAprovada()
  evidencia.criterios.focus_visibility_and_not_obscured.status = 'failed'
  evidencia.criterios.focus_visibility_and_not_obscured.evidencia.sem_indicador_de_foco = [
    { rota: '/', caminho: 'body > button:nth-child(1)', tag: 'button' },
  ]

  const resultado = validarEvidencia(evidencia, FONTE_LIMPA)
  assert.equal(resultado.status, 'failed')
  assert.ok(resultado.erros.some((erro) => erro.includes('sem_indicador_de_foco')))
})

test('reprova quando há armadilha de teclado', () => {
  const evidencia = evidenciaAprovada()
  evidencia.criterios.keyboard_navigation.status = 'failed'
  evidencia.criterios.keyboard_navigation.evidencia.armadilhas = [
    { rota: '/relatorios', motivo: 'ciclo_de_tabulacao_nao_fechou' },
  ]

  const resultado = validarEvidencia(evidencia, FONTE_LIMPA)
  assert.equal(resultado.status, 'failed')
  assert.ok(resultado.erros.some((erro) => erro.includes('armadilhas')))
})

test('reprova execução vazia em vez de tratá-la como aprovação', () => {
  const evidencia = evidenciaAprovada({ paradas_de_tabulacao_avaliadas: 0 })
  const resultado = validarEvidencia(evidencia, FONTE_LIMPA)
  assert.equal(resultado.status, 'failed')
  assert.ok(resultado.erros.some((erro) => erro.includes('Nenhuma parada de tabulação')))
})

test('reprova critério ausente na evidência', () => {
  const evidencia = evidenciaAprovada()
  delete evidencia.criterios.focus_visibility_and_not_obscured

  const resultado = validarEvidencia(evidencia, FONTE_LIMPA)
  assert.equal(resultado.status, 'failed')
  assert.ok(resultado.erros.some((erro) => erro.includes('Critério ausente')))
})

test('reprova entrada que não foi comprovada apenas por teclado', () => {
  const evidencia = evidenciaAprovada()
  evidencia.criterios.keyboard_navigation.evidencia.login_somente_teclado.alcancado_por_tabulacao = false

  const resultado = validarEvidencia(evidencia, FONTE_LIMPA)
  assert.equal(resultado.status, 'failed')
  assert.ok(resultado.erros.some((erro) => erro.includes('SC 2.1.1')))
})

test('reprova gate que introduz allowlist', () => {
  const resultado = validarEvidencia(
    evidenciaAprovada(),
    'const ALLOWLIST_ROTAS = ["/relatorios"]',
  )
  assert.equal(resultado.status, 'failed')
  assert.ok(resultado.erros.some((erro) => erro.includes('allowlist')))
})

test('reprova quando o código do gate não pode ser lido', () => {
  const resultado = validarEvidencia(evidenciaAprovada(), null)
  assert.equal(resultado.status, 'failed')
  assert.ok(resultado.erros.some((erro) => erro.includes('não pôde ser lido')))
})

test('reprova evidência ausente', () => {
  const resultado = validarEvidencia(null, FONTE_LIMPA)
  assert.equal(resultado.status, 'failed')
})

test('reprova versão de esquema divergente', () => {
  const resultado = validarEvidencia(evidenciaAprovada({ schema_version: 2 }), FONTE_LIMPA)
  assert.equal(resultado.status, 'failed')
  assert.ok(resultado.erros.some((erro) => erro.includes('esquema')))
})
