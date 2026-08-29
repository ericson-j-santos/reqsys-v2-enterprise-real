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

test('ignora documentação e comentários Vue fora do template e script', () => {
  const source = `<!--
    Exemplo interno: <PageHeader title="Pipeline" />
    Status, branch, merge e dashboard são termos técnicos desta documentação.
  -->
  <template><h1>Fluxo operacional</h1></template>
  <script setup>
  const codigoInterno = 'pipeline-status'
  </script>`

  const violations = findViolationsInFile('/tmp/ComComentario.vue', source)
  assert.equal(violations.length, 0)
})

test('continua validando mensagens reais dentro do script Vue', () => {
  const source = `<template><h1>Fluxo operacional</h1></template>
  <script setup>
  const mensagem = 'Status do dashboard'
  </script>`

  const violations = findViolationsInFile('/tmp/ComScript.vue', source)
  assert.deepEqual(
    violations.map((item) => item.term),
    ['dashboard', 'status'],
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
