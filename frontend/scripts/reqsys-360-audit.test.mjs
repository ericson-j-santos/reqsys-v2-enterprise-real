import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { analyzeProject, e2eEvidence, extractInternalDestinations, markerInventory, parseRouter, pathResolves } from './reqsys-360-audit.mjs'

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

test('inventário de dívida ignora todo, Método, placeholder e modo mock fora de comentário', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'reqsys-360-hygiene-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  write(path.join(root, 'src/views/Hygiene.vue'), `
<template>
  <p>Aplica em todo o app</p>
  <label>Método</label>
  <input placeholder="Digite aqui" />
</template>
<script>
const modo = 'mock'
// TODO revisar tratamento de erro
</script>
`)
  assert.deepEqual(markerInventory(root), [{ marker: 'TODO', file: 'src/views/Hygiene.vue', line: 9 }])
})

test('densidade considera subgrupos renderizados e não o total bruto do tema', async (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'reqsys-360-density-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  const routeLines = Array.from({ length: 10 }, (_, index) => `  { path: '/r${index + 1}', component: V${index + 1} },`).join('\n')
  const itemLines = Array.from({ length: 10 }, (_, index) => `      { to: '/r${index + 1}', title: 'R${index + 1}' },`).join('\n')
  write(path.join(root, 'src/router/index.js'), `export const routes = [\n${routeLines}\n  { path: '/:pathMatch(.*)*', component: NotFoundView, meta: { public: true } }\n]\n`)
  write(path.join(root, 'src/constants/navCatalog.js'), `
export const NAV_TEMAS = [{
  id: 'admin', title: 'Administração',
  subgroups: [
    { id: 'a', paths: ['/r1','/r2','/r3','/r4','/r5'] },
    { id: 'b', paths: ['/r6','/r7','/r8','/r9','/r10'] }
  ],
  items: [
${itemLines}
  ]
}]
`)
  write(path.join(root, 'tests/e2e/routes.spec.js'), 'function carregarRotasCanonicas() { return [] }')
  const report = await analyzeProject(root)
  assert.equal(report.summary.nav_max_effective_group, 5)
  assert.ok(!report.findings.some((item) => item.code === 'NAV_DENSITY'))
})

test('decisões governadas classificam duplicidade e reutilização sem aviso aberto', async (t) => {
  const root = fixture()
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  write(path.join(root, 'src/router/index.js'), readFile(path.join(root, 'src/router/index.js')).replace(
    "{ path: '/home', component: DashboardView, meta: { recurso: 'dashboard:read' } },",
    "{ path: '/home', component: DashboardView, meta: { recurso: 'dashboard:read' } },\n  { path: '/pipeline', component: PipelineView },\n  { path: '/qualidade-ia', component: QualidadeIAView },",
  ))
  write(path.join(root, 'src/constants/navCatalog.js'), readFile(path.join(root, 'src/constants/navCatalog.js')).replace(
    "{ to: '/pipeline', title: 'Pipeline' },",
    "{ to: '/pipeline', title: 'Pipeline' },\n      { to: '/requisitos', title: 'Atalho Requisitos' },",
  ).replace("paths: ['/pipeline', '/qualidade-ia']", "paths: ['/pipeline', '/qualidade-ia', '/requisitos']"))
  write(path.join(root, 'governance/reqsys-360/route-responsibilities.json'), JSON.stringify({
    navigation_duplicate_decisions: [
      { route: '/requisitos', classification: 'intentional-cross-theme-entry', rationale: 'atalho diário e área especializada' },
    ],
    component_reuse_decisions: [
      { component: 'DashboardView', paths: ['/', '/home'], classification: 'intentional-transitional-shell', rationale: 'compatibilidade' },
    ],
  }))

  const report = await analyzeProject(root)
  assert.ok(report.findings.some((item) => item.code === 'NAV_DUPLICATE_CLASSIFIED'))
  assert.ok(report.findings.some((item) => item.code === 'ROUTE_COMPONENT_REUSE_CLASSIFIED'))
  assert.ok(!report.findings.some((item) => item.code === 'NAV_DUPLICATE_DESTINATION' && item.path === '/requisitos'))
  assert.ok(!report.findings.some((item) => item.code === 'ROUTE_COMPONENT_REUSED' && item.component === 'DashboardView'))
})

test('E2E por catálogo é classificado sem fingir referência direta', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'reqsys-360-e2e-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  write(path.join(root, 'tests/e2e/responsividade.spec.js'), 'function carregarRotasCanonicas() { return [] }')
  const evidence = e2eEvidence(root, '/rota-nao-literal')
  assert.equal(evidence.classification, 'catalog-driven')
  assert.deepEqual(evidence.files, ['tests/e2e/responsividade.spec.js'])
})
