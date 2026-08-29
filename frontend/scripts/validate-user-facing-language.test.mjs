import assert from 'node:assert/strict'
import test from 'node:test'
import { findForbiddenTerms, findViolationsInFile } from './validate-user-facing-language.mjs'

test('detecta termos proibidos em texto visível', () => {
  const hits = findForbiddenTerms('Ver dashboard e status do runtime')
  assert.deepEqual(hits.map((item) => item.id), ['runtime', 'dashboard', 'status'])
})

test('não bloqueia nomes próprios permitidos', () => {
  const hits = findForbiddenTerms('GitHub, Teams, Planner, Power Automate, Power Apps, Figma e Copilot')
  assert.equal(hits.length, 0)
})

test('ignora identificadores técnicos e encontra texto de tela', () => {
  const source = `<template>
    <section class="agile-runtime-page" data-testid="route-agile-runtime">
      <h1>Dashboard operacional</h1>
      <button @click="abrirBranch">Abrir branch</button>
      <span>{{ item.status }}</span>
    </section>
  </template>`

  const violations = findViolationsInFile('/tmp/Exemplo.vue', source)
  assert.deepEqual(
    violations.map((item) => item.term),
    ['dashboard', 'branch'],
  )
})

test('valida propriedades de interface sem bloquear rotas internas', () => {
  const source = `export const itens = [
    { path: '/agile-runtime', titulo: 'Acompanhamento da entrega' },
    { path: '/analytics', titulo: 'Analytics' },
  ]`

  const violations = findViolationsInFile('/tmp/catalogo.js', source)
  assert.equal(violations.length, 1)
  assert.equal(violations[0].term, 'analytics')
})
