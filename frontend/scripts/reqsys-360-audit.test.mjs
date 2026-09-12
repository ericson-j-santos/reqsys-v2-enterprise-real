import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { analyzeProject, extractInternalDestinations, parseRouter, pathResolves } from './reqsys-360-audit.mjs'

function write(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, content)
}

function readFile(file) {
  return fs.readFileSync(file, 'utf8')
}

function fixture({ hiddenSubgroup = false, brokenDestination = false } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'reqsys-360-'))
  write(path.join(root, 'src/router/index.js'), `
export const routes = [
  { path: '/', component: DashboardView, meta: { recurso: 'dashboard:read' } },
  { path: '/requisitos', alias: '/requisitos/coleta', component: RequisitosView, meta: { recurso: 'requisitos:write' } },
  { path: '/painel-integracao', alias: '/notificacoes', component: PainelIntegracaoView, meta: { recurso: 'dashboard:read' } },
  { path: '/estatisticas/:indicadorId', component: EstatisticaDetalheView, meta: { recurso: 'dashboard:read' } },
  { path: '/home', component: DashboardView, meta: { recurso: 'dashboard:read' } },
  { path: '/login', component: LoginView, meta: { public: true } },
  { path: '/:pathMatch(.*)*', component: NotFoundView, meta: { public: true } }
]
`)

  const pipelinePaths = hiddenSubgroup ? "['/pipeline']" : "['/pipeline', '/qualidade-ia']"
  write(path.join(root, 'src/constants/navCatalog.js'), `
export const NAV_TEMAS = [
  {
    id: 'trabalho',
    title: 'Meu trabalho',
    items: [
      { to: '/', title: 'Painel' },
      { to: '/requisitos', title: 'Requisitos' },
      { to: '/painel-integracao', title: 'Integrações' }
    ]
  },
  {
    id: 'requisitos',
    title: 'Engenharia de requisitos',
    subgroups: [
      { id: 'pipeline', title: 'Pipeline', paths: ${pipelinePaths} }
    ],
    items: [
      { to: '/pipeline', title: 'Pipeline' },
      { to: '/qualidade-ia', title: 'Qualidade IA' }
    ]
  }
]
`)

  const destination = brokenDestination ? '/rota-inexistente' : '/notificacoes'
  write(path.join(root, 'src/views/DashboardView.vue'), `<template><a to="/requisitos/coleta">Coleta</a></template>\n<script>const x = () => irPara({ path: '${destination}' })</script>`)
  write(path.join(root, 'tests/e2e/smoke.spec.js'), "const routes = ['/', '/requisitos', '/painel-integracao', '/home']")
  return root
}

test('parseRouter reconhece rotas, aliases e rota dinâmica', () => {
  const source = `
export const routes = [
  { path: '/', component: HomeView, meta: { public: true } },
  {
    path: '/requisitos',
    alias: ['/requisitos/coleta', '/demanda'],
    component: RequisitosView,
    meta: { recurso: 'requisitos:write' },
  },
  { path: '/estatisticas/:indicadorId', component: DetailView, meta: { recurso: 'dashboard:read' } }
]
`
  const routes = parseRouter(source)
  assert.equal(routes.length, 3)
  assert.deepEqual(routes[1].aliases, ['/requisitos/coleta', '/demanda'])
  assert.equal(routes[0].public, true)
  assert.equal(pathResolves('/estatisticas/123', routes.flatMap((route) => [route.path, ...route.aliases])), true)
})

test('extractInternalDestinations captura navegação e ignora API', () => {
  const source = `
<RouterLink to="/requisitos">Abrir</RouterLink>
<button @click="irPara({ path: '/notificacoes' })">Notificações</button>
<script>router.push('/analytics'); const api = { to: '/api/status' }</script>
`
  const destinations = extractInternalDestinations(source, 'src/Test.vue').map((item) => item.path)
  assert.ok(destinations.includes('/requisitos'))
  assert.ok(destinations.includes('/notificacoes'))
  assert.ok(destinations.includes('/analytics'))
  assert.ok(!destinations.includes('/api/status'))
})

test('auditoria falha para destino quebrado e item oculto em subgrupo', async (t) => {
  const root = fixture({ hiddenSubgroup: true, brokenDestination: true })
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  const report = await analyzeProject(root)
  const codes = report.findings.filter((item) => item.severity === 'critical').map((item) => item.code)
  assert.ok(codes.includes('INTERNAL_DESTINATION_MISSING'))
  assert.ok(codes.includes('NAV_SUBGROUP_UNREACHABLE'))
  assert.ok(codes.includes('NAV_ROUTE_MISSING'))
  assert.ok(report.summary.critical >= 3)
})

test('auditoria aceita aliases e subgrupos alcançáveis sem falsos positivos críticos', async (t) => {
  const root = fixture()
  write(path.join(root, 'src/router/index.js'), readFile(path.join(root, 'src/router/index.js')).replace(
    "{ path: '/home', component: DashboardView, meta: { recurso: 'dashboard:read' } },",
    "{ path: '/home', component: DashboardView, meta: { recurso: 'dashboard:read' } },\n  { path: '/pipeline', component: PipelineView, meta: { recurso: 'requisitos:write' } },\n  { path: '/qualidade-ia', component: QualidadeIAView, meta: { recurso: 'dashboard:read' } },",
  ))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  const report = await analyzeProject(root)
  assert.equal(report.summary.critical, 0)
  assert.ok(report.findings.some((item) => item.code === 'ROUTE_COMPONENT_REUSED'))
})

test('auditoria ignora destinos artificiais em arquivos de teste dentro de src', async (t) => {
  const root = fixture()
  write(path.join(root, 'src/router/index.js'), readFile(path.join(root, 'src/router/index.js')).replace(
    "{ path: '/home', component: DashboardView, meta: { recurso: 'dashboard:read' } },",
    "{ path: '/home', component: DashboardView, meta: { recurso: 'dashboard:read' } },\n  { path: '/pipeline', component: PipelineView, meta: { recurso: 'requisitos:write' } },\n  { path: '/qualidade-ia', component: QualidadeIAView, meta: { recurso: 'dashboard:read' } },",
  ))
  write(path.join(root, 'src/layouts/__tests__/AppLayout.test.js'), `<template><a to="/a">A</a><a to="/b">B</a></template>`)
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))

  const report = await analyzeProject(root)
  assert.equal(report.summary.critical, 0)
  assert.ok(!report.findings.some((item) => item.path === '/a' || item.path === '/b'))
})
