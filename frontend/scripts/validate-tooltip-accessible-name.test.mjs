import assert from 'node:assert/strict'
import test from 'node:test'
import { findViolationsInFile } from './validate-tooltip-accessible-name.mjs'

test('acusa tooltip com texto estático e sem nome acessível', () => {
  const source = `<template>
    <v-tooltip text="Recarrega a listagem" location="top">
      <template #activator="{ props }"><v-btn v-bind="props" /></template>
    </v-tooltip>
  </template>`

  const violations = findViolationsInFile('/tmp/Exemplo.vue', source)
  assert.equal(violations.length, 1)
  assert.equal(violations[0].line, 2)
})

test('acusa tooltip com texto dinâmico e sem nome acessível', () => {
  const source = '<v-tooltip :text="item.tip" location="right" />'
  assert.equal(findViolationsInFile('/tmp/Exemplo.vue', source).length, 1)
})

test('aceita aria-label estático e dinâmico espelhando o texto', () => {
  const estatico = '<v-tooltip text="Gravar no cofre" aria-label="Gravar no cofre" />'
  const dinamico = '<v-tooltip :text="item.tip" :aria-label="item.tip" />'
  assert.deepEqual(findViolationsInFile('/tmp/A.vue', estatico), [])
  assert.deepEqual(findViolationsInFile('/tmp/B.vue', dinamico), [])
})

test('recusa :content-props, que aplica o rótulo no elemento errado', () => {
  const source = `<v-tooltip text="Alterna o tema" :content-props="{ 'aria-label': 'Alterna o tema' }" />`
  assert.equal(findViolationsInFile('/tmp/Exemplo.vue', source).length, 1)
})

test('ignora tooltip sem texto, que não tem o que espelhar', () => {
  const source = `<v-tooltip location="top"><span>conteúdo por slot</span></v-tooltip>`
  assert.deepEqual(findViolationsInFile('/tmp/Exemplo.vue', source), [])
})

test('não confunde atributos que apenas terminam em text/aria-label', () => {
  const source = '<v-tooltip :subtext="x" :data-aria-label="y" text="Real" />'
  const violations = findViolationsInFile('/tmp/Exemplo.vue', source)
  assert.equal(violations.length, 1, 'subtext/data-aria-label não valem como texto nem como nome')
})

test('atravessa `>` dentro de expressões sem perder a tag seguinte', () => {
  const source = `<v-tooltip :text="a > b ? 'maior' : 'menor'" :aria-label="a > b ? 'maior' : 'menor'" />
    <v-tooltip text="Sem rótulo" />`
  const violations = findViolationsInFile('/tmp/Exemplo.vue', source)
  assert.equal(violations.length, 1)
  assert.equal(violations[0].line, 2)
})
