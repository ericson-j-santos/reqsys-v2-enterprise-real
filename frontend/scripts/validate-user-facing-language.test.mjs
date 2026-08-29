import assert from 'node:assert/strict'
import test from 'node:test'
import { findForbiddenTerms, findViolationsInFile } from './validate-user-facing-language.mjs'

test('detecta termos proibidos em texto visível', () => {
  const hits = findForbiddenTerms('Ver dashboard e status do runtime')
  assert.deepEqual(hits.map((item) => item.id), ['runtime', 'dashboard', 'status'])
})

test('detecta anglicismos corporativos e operacionais', () => {
  const hits = findForbiddenTerms('Workflow de deploy com feedback, roadmap e compliance')
  assert.deepEqual(hits.map((item) => item.id), ['deploy', 'workflow', 'feedback', 'roadmap', 'compliance'])
})

test('detecta jargões técnicos de interface', () => {
  assert.equal(findForbiddenTerms('Guard rails').some((item) => item.id === 'guard-rail'), true)
  assert.equal(findForbiddenTerms('JWT e rate limit').some((item) => item.id === 'jwt'), true)
  assert.equal(findForbiddenTerms('JWT e rate limit').some((item) => item.id === 'rate-limit'), true)
  assert.equal(findForbiddenTerms('correlation_id').some((item) => item.id === 'correlation-id'), true)
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
  assert.deepEqual(violations.map((item) => item.term), ['dashboard', 'branch'])
})

test('percorre template raiz com templates aninhados', () => {
  const source = `<template>
    <section>
      <template #actions><button>Atualizar</button></template>
      <p>Dashboard operacional</p>
    </section>
  </template>`
  const violations = findViolationsInFile('/tmp/Aninhado.vue', source)
  assert.equal(violations.some((item) => item.term === 'dashboard'), true)
})

test('ignora exemplos de template dentro de comentários', () => {
  const source = `<!-- Exemplo: <template><PageHeader title="Pipeline" /></template> -->
  <template><section><h1>Painel</h1></section></template>`
  assert.equal(findViolationsInFile('/tmp/Comentario.vue', source).length, 0)
})

test('valida atributos visíveis de componentes', () => {
  const source = `<template><PageHeader subtitle="Runtime com JWT e rate limit" chip-tooltip="Status do serviço" /></template>`
  const terms = findViolationsInFile('/tmp/Atributos.vue', source).map((item) => item.term)
  assert.equal(terms.includes('runtime'), true)
  assert.equal(terms.includes('jwt'), true)
  assert.equal(terms.includes('rate-limit'), true)
  assert.equal(terms.includes('status'), true)
})

test('detecta literais de script que viram rótulos', () => {
  const source = `<template><span>{{ situacao }}</span></template>
<script setup>const situacao = computed(() => conectado.value ? 'Online' : 'Offline')</script>`
  const terms = findViolationsInFile('/tmp/Literal.vue', source).map((item) => item.term)
  assert.deepEqual(terms, ['online', 'offline'])
})

test('ignora blocos de comandos executáveis', () => {
  const source = `<template><section><pre>cd backend && npm run build</pre><code>git checkout branch</code><p>Painel aprovado</p></section></template>`
  assert.equal(findViolationsInFile('/tmp/Comandos.vue', source).length, 0)
})

test('ignora caminhos de membro e identificadores compostos', () => {
  assert.equal(findForbiddenTerms('itemSelecionado.status').length, 0)
  assert.equal(findForbiddenTerms('Especificações de funcionalidades · my-first-spec-project').length, 0)
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
