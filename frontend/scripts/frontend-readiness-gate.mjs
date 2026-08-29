import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()
const routerFile = path.join(root, 'src/router/index.js')
const viewsDir = path.join(root, 'src/views')
const e2eDir = path.join(root, 'tests/e2e')
const baselineFile = path.join(root, 'readiness-baseline.json')
const outputDir = path.join(root, 'artifacts/frontend-readiness')

function read(file) {
  return fs.readFileSync(file, 'utf8')
}

function walk(dir) {
  if (!fs.existsSync(dir)) return []
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    return entry.isDirectory() ? walk(full) : [full]
  })
}

function parseImports(source) {
  const imports = new Map()
  const regex = /import\s+([A-Za-z0-9_]+)\s+from\s+['"]\.\.\/views\/([^'"]+)['"]/g
  for (const match of source.matchAll(regex)) imports.set(match[1], match[2])
  return imports
}

function parseRoutes(source) {
  const routes = []
  const regex = /\{\s*path:\s*['"]([^'"]+)['"][\s\S]*?component:\s*([A-Za-z0-9_]+)[\s\S]*?meta:\s*\{([^}]*)\}[\s\S]*?\}/g
  for (const match of source.matchAll(regex)) {
    routes.push({ path: match[1], component: match[2], meta: match[3] })
  }
  return routes.filter((route) => !route.path.includes(':pathMatch'))
}

function routeCovered(routePath, e2eText) {
  if (routePath.includes(':')) {
    const prefix = routePath.split('/:')[0]
    return e2eText.includes(prefix)
  }
  return e2eText.includes(`'${routePath}'`) || e2eText.includes(`"${routePath}"`) || e2eText.includes(`\`${routePath}\``)
}

function loadBaseline() {
  if (!fs.existsSync(baselineFile)) return { allowed_unproven_routes: [] }
  return JSON.parse(read(baselineFile))
}

function classify(route, imports, e2eText, baseline) {
  const viewFile = imports.get(route.component)
  const viewExists = Boolean(viewFile && fs.existsSync(path.join(viewsDir, viewFile)))
  if (!viewExists) {
    return { status: 'vermelho', reason: `Componente ${route.component} não encontrado` }
  }

  if (routeCovered(route.path, e2eText)) {
    return { status: 'verde', reason: 'Rota possui evidência E2E no repositório' }
  }

  if (baseline.allowed_unproven_routes.includes(route.path)) {
    return { status: 'amarelo', reason: 'Rota existente sem evidência E2E; dívida conhecida no baseline' }
  }

  return { status: 'vermelho', reason: 'Nova rota sem evidência E2E e fora do baseline' }
}

function markdown(report) {
  const lines = [
    '# Gate de prontidão do frontend',
    '',
    `- Total de rotas: **${report.summary.total}**`,
    `- 🟢 Funcionando com evidência E2E: **${report.summary.verde}**`,
    `- 🟡 Não comprovado (dívida conhecida): **${report.summary.amarelo}**`,
    `- 🔴 Falha/bloqueio: **${report.summary.vermelho}**`,
    '',
    '| Estado | Rota | Componente | Evidência |',
    '|---|---|---|---|',
  ]
  for (const item of report.routes) {
    const icon = item.status === 'verde' ? '🟢' : item.status === 'amarelo' ? '🟡' : '🔴'
    lines.push(`| ${icon} | \`${item.path}\` | \`${item.component}\` | ${item.reason} |`)
  }
  lines.push('', `Gerado em: ${report.generated_at}`)
  return `${lines.join('\n')}\n`
}

function main() {
  const source = read(routerFile)
  const imports = parseImports(source)
  const routes = parseRoutes(source)
  const e2eText = walk(e2eDir).filter((f) => /\.(js|ts|mjs|cjs)$/.test(f)).map(read).join('\n')
  const baseline = loadBaseline()

  const result = routes.map((route) => ({
    ...route,
    ...classify(route, imports, e2eText, baseline),
  }))

  const summary = {
    total: result.length,
    verde: result.filter((r) => r.status === 'verde').length,
    amarelo: result.filter((r) => r.status === 'amarelo').length,
    vermelho: result.filter((r) => r.status === 'vermelho').length,
  }

  const report = {
    schema_version: 1,
    generated_at: new Date().toISOString(),
    summary,
    routes: result,
  }

  fs.mkdirSync(outputDir, { recursive: true })
  fs.writeFileSync(path.join(outputDir, 'frontend-readiness.json'), `${JSON.stringify(report, null, 2)}\n`)
  fs.writeFileSync(path.join(outputDir, 'frontend-readiness.md'), markdown(report))

  console.log(markdown(report))
  if (summary.vermelho > 0) process.exitCode = 1
}

main()
