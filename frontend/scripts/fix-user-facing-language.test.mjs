import assert from 'node:assert/strict'
import test from 'node:test'
import {
  isLikelyHumanLiteral,
  isTechnicalSelectorOrIdentifier,
  transformJavascript,
  transformVue,
} from './fix-user-facing-language.mjs'

test('não mexe em template literal aninhado (endereço de serviço real)', () => {
  const source = [
    'async function carregar() {',
    "  const endpoint = `${getApiBaseUrl()}/api/requisitos/workspace${query ? `?${query}` : ''}`",
    '  return endpoint',
    '}',
  ].join('\n')

  const after = transformJavascript(source)
  assert.equal(after, source)
})

test('isLikelyHumanLiteral rejeita fatia de template literal com interpolação sem fechar', () => {
  assert.equal(
    isLikelyHumanLiteral("${getApiBaseUrl()}/api/requisitos/workspace${query ? "),
    false,
  )
})

test('isLikelyHumanLiteral ainda aceita texto humano com uma interpolação simples', () => {
  assert.equal(isLikelyHumanLiteral('Você tem ${count} pendências'), true)
})

test('não traduz seletor CSS com data-testid nem classe técnica', () => {
  const selector = '[data-testid="route-specs"] .content-body'
  assert.equal(isTechnicalSelectorOrIdentifier(selector), true)
  assert.equal(isLikelyHumanLiteral(selector), false)

  const source = `const selector = '${selector}'`
  assert.equal(transformJavascript(source), source)
})

test('não traduz identificador técnico route-specs', () => {
  assert.equal(isTechnicalSelectorOrIdentifier('route-specs'), true)
  assert.equal(isLikelyHumanLiteral('route-specs'), false)
})

test('ainda simplifica termos em texto de tela dentro do template', () => {
  const source = '<template><h1>Painel de status do runtime</h1></template>'
  const after = transformVue(source)
  assert.match(after, /situação/)
  assert.match(after, /execução/)
})
