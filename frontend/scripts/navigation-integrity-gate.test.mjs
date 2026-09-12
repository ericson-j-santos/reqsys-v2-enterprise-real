import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import test from 'node:test'

function prepararProjeto({ brokenLink = false, brokenRedirect = false } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'reqsys-navigation-gate-'))
  fs.mkdirSync(path.join(root, 'src/router'), { recursive: true })
  fs.mkdirSync(path.join(root, 'src/constants'), { recursive: true })
  fs.mkdirSync(path.join(root, 'src/views'), { recursive: true })
  fs.mkdirSync(path.join(root, 'scripts'), { recursive: true })

  const script = fs.readFileSync(new URL('./navigation-integrity-gate.mjs', import.meta.url), 'utf8')
  fs.writeFileSync(path.join(root, 'scripts/navigation-integrity-gate.mjs'), script)

  fs.writeFileSync(path.join(root, 'src/router/index.js'), `
export const routes = [
  { path: '/', component: HomeView, meta: {} },
  { path: '/requisitos', component: RequisitosView, meta: {} },
  { path: '/painel-integracao', component: PainelIntegracaoView, meta: {} },
  { path: '/requisitos/coleta', redirect: '/requisitos' },
  { path: '/notificacoes', redirect: '${brokenRedirect ? '/destino-inexistente' : '/painel-integracao'}' },
]
`)

  fs.writeFileSync(path.join(root, 'src/constants/navCatalog.js'), `
export const NAV_TEMAS = [{ items: [{ to: '/requisitos' }, { to: '/painel-integracao' }] }]
`)

  fs.writeFileSync(path.join(root, 'src/views/HomeView.vue'), `
<template>
  <a to="/requisitos/coleta">Nova demanda</a>
  <a to="/notificacoes">Notificações</a>
  ${brokenLink ? '<a to="/fantasma">Quebrado</a>' : ''}
</template>
<script setup>
const rota = { path: '/requisitos' }
function abrir() { router.push('/painel-integracao') }
</script>
`)

  return root
}

function executar(root) {
  return spawnSync(process.execPath, ['scripts/navigation-integrity-gate.mjs'], {
    cwd: root,
    encoding: 'utf8',
  })
}

function lerRelatorio(root) {
  return JSON.parse(fs.readFileSync(path.join(root, 'artifacts/navigation-integrity/navigation-integrity.json'), 'utf8'))
}

test('aprova quando todos os destinos internos possuem rota ou redirecionamento válido', () => {
  const root = prepararProjeto()
  const result = executar(root)
  assert.equal(result.status, 0, result.stderr || result.stdout)
  const report = lerRelatorio(root)
  assert.equal(report.summary.missing, 0)
})

test('falha quando um link interno aponta para rota inexistente', () => {
  const root = prepararProjeto({ brokenLink: true })
  const result = executar(root)
  assert.notEqual(result.status, 0)
  const report = lerRelatorio(root)
  assert.deepEqual(report.missing_destinations.map((item) => item.destination), ['/fantasma'])
})

test('falha quando um redirecionamento aponta para destino inexistente', () => {
  const root = prepararProjeto({ brokenRedirect: true })
  const result = executar(root)
  assert.notEqual(result.status, 0)
  const report = lerRelatorio(root)
  assert.ok(report.missing_destinations.some((item) => item.destination === '/destino-inexistente' && item.kind === 'redirect'))
})
