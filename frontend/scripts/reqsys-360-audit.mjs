import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { pathToFileURL } from 'node:url'

const DEFAULT_MAX_NAV_ITEMS = 8

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

function parseRouteBlock(block) {
  const pathMatch = block.match(/\bpath\s*:\s*['"]([^'"]+)['"]/)
  if (!pathMatch) return null

  const component = block.match(/\bcomponent\s*:\s*([A-Za-z0-9_]+)/)?.[1] ?? null
  const meta = block.match(/\bmeta\s*:\s*\{([^}]*)\}/s)?.[1] ?? ''
  const aliasExpression = block.match(/\balias\s*:\s*(\[[^\]]*\]|['"][^'"]+['"])/s)?.[1] ?? ''
  const aliases = [...aliasExpression.matchAll(/['"]([^'"]+)['"]/g)].map((match) => match[1])

  return {
    path: pathMatch[1],
    component,
    aliases,
    public: /\bpublic\s*:\s*true\b/.test(meta),
  }
}

export function parseRouter(source) {
  const lines = source.split(/\r?\n/)
  const routes = []
  let insideRoutes = false
  let current = []

  for (const line of lines) {
    if (!insideRoutes && line.includes('export const routes = [')) {
      insideRoutes = true
      continue
    }
    if (!insideRoutes) continue
    if (!current.length && /^\s{2}\]\s*$/.test(line)) break

    if (!current.length && /^\s{2}\{/.test(line)) {
      current = [line]
      if (/\}\s*,?\s*$/.test(line)) {
        const parsed = parseRouteBlock(current.join('\n'))
        if (parsed) routes.push(parsed)
        current = []
      }
      continue
    }

    if (current.length) {
      current.push(line)
      if (/^\s{2}\}\s*,?\s*$/.test(line)) {
        const parsed = parseRouteBlock(current.join('\n'))
        if (parsed) routes.push(parsed)
        current = []
      }
    }
  }

  return routes
}

function normalisePath(value) {
  if (!value) return value
  const withoutQuery = value.split(/[?#]/, 1)[0]
  if (withoutQuery === '/') return '/'
  return withoutQuery.replace(/\/+$/, '') || '/'
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function routeRegex(routePath) {
  const normalised = normalisePath(routePath)
  if (!normalised || normalised.includes(':pathMatch')) return null
  if (normalised === '/') return /^\/$/

  const segments = normalised.split('/').slice(1).map((segment) => {
    if (segment.startsWith(':')) return '[^/]+'
    return escapeRegex(segment)
  })
  return new RegExp(`^/${segments.join('/')}$`)
}

export function pathResolves(candidate, routePatterns) {
  const normalised = normalisePath(candidate)
  return routePatterns.some((pattern) => routeRegex(pattern)?.test(normalised))
}

function lineNumber(source, index) {
  return source.slice(0, index).split(/\r?\n/).length
}

export function extractInternalDestinations(source, file) {
  const definitions = [
    ['to-attribute', /\bto\s*=\s*['"](\/[^'"\s<>]*)['"]/g],
    ['to-property', /\bto\s*:\s*['"`](\/[^'"`\s}]*)['"`]/g],
    ['router-push', /\b(?:router|\$router)\.(?:push|replace)\(\s*['"`](\/[^'"`\s)]*)['"`]/g],
    ['ir-para-string', /\birPara\(\s*['"`](\/[^'"`\s)]*)['"`]/g],
    ['ir-para-path', /\birPara\(\s*\{[\s\S]{0,160}?\bpath\s*:\s*['"`](\/[^'"`\s}]*)['"`]/g],
    ['internal-href', /\bhref\s*=\s*['"](\/[^'"\s<>]*)['"]/g],
  ]

  const found = []
  for (const [kind, regex] of definitions) {
    for (const match of source.matchAll(regex)) {
      const value = match[1]
      if (!value || value.startsWith('/api/') || value === '/api') continue
      found.push({
        path: value,
        kind,
        file,
        line: lineNumber(source, match.index ?? 0),
      })
    }
  }

  const deduplicated = new Map()
  for (const item of found) {
    const key = `${item.file}:${item.line}:${item.kind}:${item.path}`
    deduplicated.set(key, item)
  }
  return [...deduplicated.values()]
}

async function loadNavCatalog(root) {
  const file = path.join(root, 'src/constants/navCatalog.js')
  const source = read(file)
  const dataUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
  const module = await import(dataUrl)
  return module.NAV_TEMAS ?? []
}

function e2eEvidence(root, routePath) {
  const e2eDir = path.join(root, 'tests/e2e')
  const text = walk(e2eDir)
    .filter((file) => /\.(?:js|ts|mjs|cjs)$/.test(file))
    .map(read)
    .join('\n')

  if (!text) return false
  if (routePath.includes(':')) {
    const prefix = routePath.split('/:')[0]
    return Boolean(prefix && text.includes(prefix))
  }
  return text.includes(`'${routePath}'`) || text.includes(`"${routePath}"`) || text.includes(`\`${routePath}\``)
}

function markerInventory(root) {
  const markerRegex = /\b(TODO|FIXME|HACK|PLACEHOLDER|MOCK)\b/gi
  const items = []
  for (const file of walk(path.join(root, 'src')).filter((item) => /\.(?:vue|js|ts|mjs|cjs)$/.test(item))) {
    const source = read(file)
    for (const match of source.matchAll(markerRegex)) {
      items.push({
        marker: match[1].toUpperCase(),
        file: path.relative(root, file).replaceAll('\\', '/'),
        line: lineNumber(source, match.index ?? 0),
      })
    }
  }
  return items
}

function finding(severity, code, message, details = {}) {
  return { severity, code, message, ...details }
}

export async function analyzeProject(root) {
  const routerFile = path.join(root, 'src/router/index.js')
  const routes = parseRouter(read(routerFile))
  const primaryRoutes = routes.filter((route) => !route.path.includes(':pathMatch'))
  const routePatterns = primaryRoutes.flatMap((route) => [route.path, ...route.aliases])
  const navThemes = await loadNavCatalog(root)
  const navItems = navThemes.flatMap((theme) => theme.items.map((item) => ({ ...item, themeId: theme.id, themeTitle: theme.title })))
  const findings = []

  for (const item of navItems) {
    if (!pathResolves(item.to, routePatterns)) {
      findings.push(finding('critical', 'NAV_ROUTE_MISSING', `Item de navegação aponta para rota inexistente: ${item.to}`, {
        path: item.to,
        theme: item.themeId,
      }))
    }
  }

  for (const theme of navThemes.filter((item) => item.subgroups?.length)) {
    const subgroupPaths = new Set(theme.subgroups.flatMap((subgroup) => subgroup.paths ?? []))
    for (const item of theme.items) {
      if (!subgroupPaths.has(item.to)) {
        findings.push(finding('critical', 'NAV_SUBGROUP_UNREACHABLE', `Item ${item.to} está cadastrado em ${theme.title}, mas não pertence a nenhum subgrupo renderizável.`, {
          path: item.to,
          theme: theme.id,
        }))
      }
    }
  }

  const ignoredSourceFiles = new Set([
    path.normalize('src/router/index.js'),
    path.normalize('src/constants/navCatalog.js'),
  ])
  const internalDestinations = []
  for (const absoluteFile of walk(path.join(root, 'src')).filter((file) => /\.(?:vue|js|ts|mjs|cjs)$/.test(file))) {
    const relativeFile = path.relative(root, absoluteFile)
    if (ignoredSourceFiles.has(path.normalize(relativeFile))) continue
    internalDestinations.push(...extractInternalDestinations(read(absoluteFile), relativeFile.replaceAll('\\', '/')))
  }

  for (const destination of internalDestinations) {
    if (!pathResolves(destination.path, routePatterns)) {
      findings.push(finding('critical', 'INTERNAL_DESTINATION_MISSING', `Destino interno não resolve para rota declarada: ${destination.path}`, destination))
    }
  }

  const navByPath = new Map()
  for (const item of navItems) {
    const bucket = navByPath.get(item.to) ?? []
    bucket.push(`${item.themeId}:${item.title}`)
    navByPath.set(item.to, bucket)
  }
  for (const [routePath, owners] of navByPath) {
    if (owners.length > 1) {
      findings.push(finding('warning', 'NAV_DUPLICATE_DESTINATION', `A rota ${routePath} aparece ${owners.length} vezes no catálogo de navegação.`, {
        path: routePath,
        owners,
      }))
    }
  }

  const components = new Map()
  for (const route of primaryRoutes.filter((item) => item.component)) {
    const bucket = components.get(route.component) ?? []
    bucket.push(route.path)
    components.set(route.component, bucket)
  }
  for (const [component, paths] of components) {
    if (paths.length > 1) {
      findings.push(finding('warning', 'ROUTE_COMPONENT_REUSED', `O componente ${component} atende múltiplas rotas; classificar canônica/alias/legado.`, {
        component,
        paths,
      }))
    }
  }

  const navPaths = new Set(navItems.map((item) => normalisePath(item.to)))
  for (const route of primaryRoutes) {
    if (route.public || route.path.includes(':') || navPaths.has(normalisePath(route.path))) continue
    findings.push(finding('info', 'ROUTE_OUTSIDE_PRIMARY_NAV', `Rota ${route.path} não aparece no catálogo principal.`, {
      path: route.path,
      component: route.component,
    }))
  }

  for (const theme of navThemes) {
    if (theme.items.length > DEFAULT_MAX_NAV_ITEMS) {
      findings.push(finding('warning', 'NAV_DENSITY', `${theme.title} possui ${theme.items.length} itens no mesmo nível.`, {
        theme: theme.id,
        count: theme.items.length,
        threshold: DEFAULT_MAX_NAV_ITEMS,
      }))
    }
  }

  let e2eProven = 0
  let e2eUnproven = 0
  for (const route of primaryRoutes.filter((item) => !item.public)) {
    if (e2eEvidence(root, route.path)) {
      e2eProven += 1
    } else {
      e2eUnproven += 1
      findings.push(finding('warning', 'ROUTE_WITHOUT_E2E_REFERENCE', `Rota ${route.path} não possui referência E2E detectável no repositório.`, {
        path: route.path,
      }))
    }
  }

  const markers = markerInventory(root)
  const summary = {
    routes: primaryRoutes.length,
    aliases: primaryRoutes.reduce((total, route) => total + route.aliases.length, 0),
    nav_items: navItems.length,
    nav_unique_paths: new Set(navItems.map((item) => item.to)).size,
    internal_destinations: internalDestinations.length,
    e2e_proven_routes: e2eProven,
    e2e_unproven_routes: e2eUnproven,
    hygiene_markers: markers.length,
    critical: findings.filter((item) => item.severity === 'critical').length,
    warning: findings.filter((item) => item.severity === 'warning').length,
    info: findings.filter((item) => item.severity === 'info').length,
  }

  return {
    schema_version: 1,
    generated_at: new Date().toISOString(),
    summary,
    findings,
    hygiene_markers: markers.slice(0, 200),
  }
}

function sanitise(value) {
  return String(value ?? '').replaceAll('|', '\\|').replaceAll('\n', ' ')
}

export function markdown(report) {
  const lines = [
    '# ReqSys 360 — Auditoria de Coerência Funcional',
    '',
    `- Rotas: **${report.summary.routes}** (+ ${report.summary.aliases} aliases)`,
    `- Itens de navegação: **${report.summary.nav_items}** (${report.summary.nav_unique_paths} destinos únicos)`,
    `- Destinos internos encontrados: **${report.summary.internal_destinations}**`,
    `- E2E detectável: **${report.summary.e2e_proven_routes}** comprovadas / **${report.summary.e2e_unproven_routes}** sem referência`,
    `- Marcadores de higiene: **${report.summary.hygiene_markers}**`,
    `- Críticos: **${report.summary.critical}** · Avisos: **${report.summary.warning}** · Informativos: **${report.summary.info}**`,
    '',
    '| Severidade | Código | Mensagem |',
    '|---|---|---|',
  ]

  for (const item of report.findings) {
    const icon = item.severity === 'critical' ? '🔴' : item.severity === 'warning' ? '🟡' : 'ℹ️'
    lines.push(`| ${icon} ${item.severity} | \`${sanitise(item.code)}\` | ${sanitise(item.message)} |`)
  }

  if (!report.findings.length) lines.push('| 🟢 | `OK` | Nenhuma inconsistência detectada. |')
  lines.push('', `Gerado em: ${report.generated_at}`)
  return `${lines.join('\n')}\n`
}

async function main() {
  const root = process.cwd()
  const report = await analyzeProject(root)
  const outputDir = path.join(root, 'artifacts/reqsys-360')
  fs.mkdirSync(outputDir, { recursive: true })
  fs.writeFileSync(path.join(outputDir, 'reqsys-360.json'), `${JSON.stringify(report, null, 2)}\n`)
  fs.writeFileSync(path.join(outputDir, 'reqsys-360.md'), markdown(report))
  console.log(markdown(report))
  if (report.summary.critical > 0) process.exitCode = 1
}

const invokedDirectly = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href
if (invokedDirectly) {
  main().catch((error) => {
    console.error(`[reqsys-360] ${error.stack ?? error.message}`)
    process.exitCode = 1
  })
}
