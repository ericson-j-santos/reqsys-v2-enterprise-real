import assert from 'node:assert/strict'
import test from 'node:test'
import { isLikelyHumanLiteral, transformJavascript, transformVue } from './fix-user-facing-language.mjs'

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

test('ainda simplifica termos em texto de tela dentro do template', () => {
  const source = '<template><h1>Painel de status do runtime</h1></template>'
  const after = transformVue(source)
  assert.match(after, /situação/)
  assert.match(after, /execução/)
})
