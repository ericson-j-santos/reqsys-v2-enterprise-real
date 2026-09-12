import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()
const srcDir = path.join(root, 'src')
const routerFile = path.join(srcDir, 'router/index.js')
const outputDir = path.join(root, 'artifacts/navigation-integrity')

const STATIC_PATH_ALLOWLIST = new Set(['/auth/callback.html'])
const NON_SPA_PREFIXES = ['/api/', '/v1/']

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

function stripQueryHash(value) {
  return String(value || '').split(/[?#]/, 1)[0] || '/'
}

function isSpaCandidate(value) {
  if (!value || !value.startsWith('/')) return false
  if (value.includes('${') || value.includes(':pathMatch')) return false
  if (STATIC_PATH_ALLOWLIST.has(stripQueryHash(value))) return false
  if (value === '/api' || value === '/v1') return false
  return !NON_SPA_PREFIXES.some((prefix) => value.startsWith(prefix))
}

function isProductionSource(file) {
  if (!/\.(vue|js|ts|mjs|cjs)$/.test(file) || file === routerFile) return false
  const relative = path.relative(srcDir, file).replaceAll(path.sep, '/')
  if (relative.includes('/__tests__/') || relative.startsWith('__tests__/')) return false
  if (/\.(?:test|spec)\.[cm]?[jt]s$/.test(relative)) return false
  return true
}

function extractStringLiterals(fragment) {
  return [...fragment.matchAll(/['"]([^'"]+)['"]/g)].map((match) => match[1])
}

function parseRouterPaths(source) {
  const paths = new Set()
  for (const match of source.matchAll(/\bpath:\s*['"]([^'"]+)['"]/g)) {
    if (!match[1].includes(':pathMatch')) paths.add(stripQueryHash(match[1]))
  }
  for (const match of source.matchAll(/\balias:\s*(\[[^\]]*\]|['"][^'"]+['"])/g)) {
    for (const alias of extractStringLiterals(match[1])) paths.add(stripQueryHash(alias))
  }
  return paths
}

function routeRegex(routePath) {
  if (routePath === '/') return /^\/$/
  const escaped = routePath
    .split('/')
    .map((part) => {
      if (!part) return ''
      if (part.startsWith(':')) return '[^/]+'
      return part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    })
    .join('/')
  return new RegExp(`^${escaped}/?$`)
}

function routeExists(destination, routes) {
  const clean = stripQueryHash(destination)
  if (STATIC_PATH_ALLOWLIST.has(clean)) return true
  return [...routes].some((route) => routeRegex(route).test(clean))
}

function lineNumber(source, index) {
  return source.slice(0, index).split('\n').length
}

function collectDestinationsFromSource(source, relativePath) {
  const found = []
  const patterns = [
    { kind: 'template-to', regex: /\bto\s*=\s*["'](\/[^"']+)["']/g },
    { kind: 'property', regex: /\b(?:to|path|route|redirect)\s*:\s*['"`](\/[^'"`]+)['"`]/g },
    { kind: 'call', regex: /\b(?:router\.(?:push|replace)|goTo|irPara|navegarPara|abrirRota)\s*\(\s*['"`](\/[^'"`]+)['"`]/g },
  ]

  for (const { kind, regex } of patterns) {
    for (const match of source.matchAll(regex)) {
      const destination = match[1]
      if (!isSpaCandidate(destination)) continue
      found.push({
        destination: stripQueryHash(destination),
        source: relativePath,
        line: lineNumber(source, match.index || 0),
        kind,
      })
    }
  }
  return found
}

function collectRedirects(routerSource) {
  const found = []
  for (const match of routerSource.matchAll(/\bredirect:\s*['"`](\/[^'"`]+)['"`]/g)) {
    if (!isSpaCandidate(match[1])) continue
    found.push({
      destination: stripQueryHash(match[1]),
      source: 'src/router/index.js',
      line: lineNumber(routerSource, match.index || 0),
      kind: 'redirect',
    })
  }
  return found
}

function markdown(report) {
  const lines = [
    '# Gate de integridade de navegação',
    '',
    `- Rotas conhecidas: **${report.summary.routes}**`,
    `- Destinos internos analisados: **${report.summary.destinations}**`,
    `- Destinos inválidos: **${report.summary.missing}**`,
    `- Rotas sem referência estática conhecida: **${report.summary.unreferenced_routes}**`,
    '',
  ]

  if (report.missing_destinations.length) {
    lines.push('## Destinos inválidos', '', '| Destino | Origem | Linha | Tipo |', '|---|---|---:|---|')
    for (const item of report.missing_destinations) {
      lines.push(`| \`${item.destination}\` | \`${item.source}\` | ${item.line} | ${item.kind} |`)
    }
    lines.push('')
  } else {
    lines.push('🟢 Nenhum destino interno estático aponta para rota inexistente.', '')
  }

  if (report.unreferenced_routes.length) {
    lines.push('## Rotas sem referência estática conhecida', '')
    for (const route of report.unreferenced_routes) lines.push(`- \`${route}\``)
    lines.push('', '> Observação: esta lista é informativa; rotas profundas, públicas ou acessadas dinamicamente podem ser intencionais.', '')
  }

  lines.push(`Gerado em: ${report.generated_at}`)
  return `${lines.join('\n')}\n`
}

function main() {
  if (!fs.existsSync(routerFile)) throw new Error(`Router não encontrado: ${routerFile}`)

  const routerSource = read(routerFile)
  const routes = parseRouterPaths(routerSource)
  const sourceFiles = walk(srcDir).filter(isProductionSource)

  const destinations = sourceFiles.flatMap((file) => {
    const relative = path.relative(root, file).replaceAll(path.sep, '/')
    return collectDestinationsFromSource(read(file), relative)
  })
  destinations.push(...collectRedirects(routerSource))

  const uniqueKey = (item) => `${item.destination}|${item.source}|${item.line}|${item.kind}`
  const uniqueDestinations = [...new Map(destinations.map((item) => [uniqueKey(item), item])).values()]
  const missingDestinations = uniqueDestinations.filter((item) => !routeExists(item.destination, routes))

  const referencedPaths = new Set(uniqueDestinations.map((item) => item.destination))
  const unreferencedRoutes = [...routes]
    .filter((route) => route !== '/login' && route !== '/showcase' && route !== '/demo')
    .filter((route) => ![...referencedPaths].some((destination) => routeRegex(route).test(destination)))
    .sort()

  const report = {
    schema_version: 1,
    generated_at: new Date().toISOString(),
    summary: {
      routes: routes.size,
      destinations: uniqueDestinations.length,
      missing: missingDestinations.length,
      unreferenced_routes: unreferencedRoutes.length,
    },
    missing_destinations: missingDestinations,
    unreferenced_routes: unreferencedRoutes,
  }

  fs.mkdirSync(outputDir, { recursive: true })
  fs.writeFileSync(path.join(outputDir, 'navigation-integrity.json'), `${JSON.stringify(report, null, 2)}\n`)
  fs.writeFileSync(path.join(outputDir, 'navigation-integrity.md'), markdown(report))

  console.log(markdown(report))
  if (missingDestinations.length > 0) process.exitCode = 1
}

main()
