import assert from 'node:assert/strict'
import test from 'node:test'
import { findViolationsInFile, stripFunctionArgs } from './validate-design-token-usage.mjs'

test('acusa font-size com px hardcoded', () => {
  const source = `<style scoped>\n.card { font-size: 14px; }\n</style>`
  const violations = findViolationsInFile('/tmp/Exemplo.vue', source, 'views/Exemplo.vue')
  assert.equal(violations.length, 1)
  assert.equal(violations[0].declaracao, 'font-size: 14px')
})

test('acusa padding e margin com px hardcoded, incluindo variantes -top/-left/-inline', () => {
  const source = `<style scoped>
.a { padding: 12px; }
.b { padding-top: 8px; }
.c { margin-left: 4px; }
.d { padding-inline: 14px !important; }
</style>`
  const violations = findViolationsInFile('/tmp/Exemplo.vue', source, 'views/Exemplo.vue')
  assert.equal(violations.length, 4)
})

test('acusa style inline no template, não só bloco <style>', () => {
  const source = `<div style="font-size:11px">texto</div>`
  const violations = findViolationsInFile('/tmp/Exemplo.vue', source, 'views/Exemplo.vue')
  assert.equal(violations.length, 1)
})

test('aceita valores já usando os tokens (var/calc/clamp/rem/%)', () => {
  const source = `<style scoped>
.a { font-size: var(--font-size-base); }
.b { padding: var(--space-md) var(--space-lg); }
.c { margin: 0 auto; }
.d { font-size: 0.875rem; }
.e { padding: 50%; }
.f { font-size: clamp(24px, 4vw, 38px); }
</style>`
  assert.deepEqual(findViolationsInFile('/tmp/Exemplo.vue', source, 'views/Exemplo.vue'), [])
})

test('literal 0 em shorthand não é hardcoded', () => {
  const source = `<style scoped>.a { margin: 0 0 var(--space-lg); }</style>`
  assert.deepEqual(findViolationsInFile('/tmp/Exemplo.vue', source, 'views/Exemplo.vue'), [])
})

test('ignora propriedades fora de escopo (width/gap/border-radius/line-height)', () => {
  const source = `<style scoped>
.a { width: 280px; gap: 12px; border-radius: 8px; line-height: 1.4; }
</style>`
  assert.deepEqual(findViolationsInFile('/tmp/Exemplo.vue', source, 'views/Exemplo.vue'), [])
})

test('exceção documentada (ArquiteturaView 106px) não é acusada; a mesma linha em outro arquivo seria', () => {
  const source = `<style scoped>.arch-arrow { padding: var(--space-xs) 0 var(--space-xs) 106px; }</style>`
  assert.deepEqual(findViolationsInFile('/tmp/A.vue', source, 'views/ArquiteturaView.vue'), [])

  const violations = findViolationsInFile('/tmp/B.vue', source, 'views/OutraView.vue')
  assert.equal(violations.length, 1, 'a mesma declaração em outro arquivo não está na allowlist e deve acusar')
})

test('stripFunctionArgs remove px de dentro de var()/calc()/clamp() sem afetar px fora deles', () => {
  assert.equal(stripFunctionArgs('var(--space-md)'), '0')
  assert.equal(stripFunctionArgs('calc(100% - 24px)'), '0')
  assert.equal(stripFunctionArgs('clamp(24px, 4vw, 38px) 10px'), '0 10px')
})
