import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { spawnSync } from 'node:child_process'

function fixture({ extraRoute = false, missingComponent = false } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'frontend-readiness-'))
  fs.mkdirSync(path.join(root, 'src/router'), { recursive: true })
  fs.mkdirSync(path.join(root, 'src/views'), { recursive: true })
  fs.mkdirSync(path.join(root, 'tests/e2e'), { recursive: true })
  fs.mkdirSync(path.join(root, 'scripts'), { recursive: true })

  const script = fs.readFileSync(new URL('./frontend-readiness-gate.mjs', import.meta.url), 'utf8')
  fs.writeFileSync(path.join(root, 'scripts/frontend-readiness-gate.mjs'), script)
  fs.writeFileSync(path.join(root, 'src/views/HomeView.vue'), '<template><div /></template>')
  if (!missingComponent) fs.writeFileSync(path.join(root, 'src/views/AdminView.vue'), '<template><div /></template>')

  const extraImport = extraRoute ? "import NovaView from '../views/NovaView.vue'\n" : ''
  if (extraRoute) fs.writeFileSync(path.join(root, 'src/views/NovaView.vue'), '<template><div /></template>')
  fs.writeFileSync(path.join(root, 'src/router/index.js'), `
import HomeView from '../views/HomeView.vue'
import AdminView from '../views/AdminView.vue'
${extraImport}
export const routes = [
  { path: '/', component: HomeView, meta: { public: true } },
  { path: '/admin', component: AdminView, meta: { recurso: 'admin' } },
  ${extraRoute ? "{ path: '/nova', component: NovaView, meta: { recurso: 'read' } }," : ''}
]
`)
  fs.writeFileSync(path.join(root, 'tests/e2e/home.spec.js'), "page.goto('/')")
  fs.writeFileSync(path.join(root, 'readiness-baseline.json'), JSON.stringify({ allowed_unproven_routes: ['/admin'] }))
  return root
}

function run(root) {
  return spawnSync(process.execPath, ['scripts/frontend-readiness-gate.mjs'], { cwd: root, encoding: 'utf8' })
}

test('mantém dívida conhecida em amarelo sem bloquear o gate', () => {
  const root = fixture()
  const result = run(root)
  assert.equal(result.status, 0)
  const report = JSON.parse(fs.readFileSync(path.join(root, 'artifacts/frontend-readiness/frontend-readiness.json')))
  assert.equal(report.summary.vermelho, 0)
  assert.ok(report.routes.some((r) => r.path === '/admin' && r.status === 'amarelo'))
})

test('bloqueia nova rota sem evidência E2E', () => {
  const root = fixture({ extraRoute: true })
  const result = run(root)
  assert.equal(result.status, 1)
  const report = JSON.parse(fs.readFileSync(path.join(root, 'artifacts/frontend-readiness/frontend-readiness.json')))
  assert.ok(report.routes.some((r) => r.path === '/nova' && r.status === 'vermelho'))
})

test('bloqueia rota cujo componente não existe', () => {
  const root = fixture({ missingComponent: true })
  const result = run(root)
  assert.equal(result.status, 1)
  const report = JSON.parse(fs.readFileSync(path.join(root, 'artifacts/frontend-readiness/frontend-readiness.json')))
  assert.ok(report.routes.some((r) => r.path === '/admin' && r.status === 'vermelho'))
})
