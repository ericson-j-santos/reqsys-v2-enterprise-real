const SQL_KEYWORDS = new Set(['select', 'from', 'where', 'join', 'inner', 'left', 'right', 'full', 'outer', 'cross', 'on', 'group', 'by', 'order', 'having', 'limit', 'offset', 'with', 'recursive', 'union', 'all', 'distinct', 'case', 'when', 'then', 'else', 'end', 'as', 'and', 'or'])

const PII_PATTERNS = [/\bcpf\b/i, /\bcnpj\b/i, /\bemail\b/i, /\btelefone\b/i, /\bcelular\b/i, /\bnome\b/i, /\bendereco\b/i, /\bconta\b/i, /\bagencia\b/i]
const DESTRUCTIVE_PATTERNS = [/\bdelete\b/i, /\bupdate\b/i, /\binsert\b/i, /\bdrop\b/i, /\btruncate\b/i, /\balter\b/i, /\bcreate\b/i, /\bgrant\b/i, /\brevoke\b/i]

export function normalizeSql(sql) {
  return String(sql || '').replace(/--.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\s+/g, ' ').trim()
}

export function splitSelectColumns(sql) {
  const selectMatch = normalizeSql(sql).match(/select\s+([\s\S]+?)\s+from\s+/i)
  if (!selectMatch) return []

  const columns = []
  let current = ''
  let depth = 0
  for (const char of selectMatch[1]) {
    if (char === '(') depth += 1
    if (char === ')') depth = Math.max(0, depth - 1)
    if (char === ',' && depth === 0) {
      columns.push(current.trim())
      current = ''
    } else {
      current += char
    }
  }
  if (current.trim()) columns.push(current.trim())
  return columns
}

function extractTables(sql) {
  const regex = /\b(?:from|join)\s+([a-zA-Z_][\w.]*)(?:\s+(?:as\s+)?([a-zA-Z_][\w]*))?/gi
  const tables = []
  let match
  while ((match = regex.exec(normalizeSql(sql))) !== null) {
    const alias = match[2] && !SQL_KEYWORDS.has(match[2].toLowerCase()) ? match[2] : null
    tables.push({ table: match[1], alias })
  }
  return tables
}

function extractJoins(sql) {
  const regex = /\b((?:inner|left|right|full|cross)?\s*join)\s+([a-zA-Z_][\w.]*)(?:\s+(?:as\s+)?([a-zA-Z_][\w]*))?(?:\s+on\s+(.+?))?(?=\s+(?:inner|left|right|full|cross)?\s*join\b|\s+where\b|\s+group\s+by\b|\s+order\s+by\b|\s+having\b|\s+limit\b|$)/gi
  const joins = []
  let match
  while ((match = regex.exec(normalizeSql(sql))) !== null) {
    joins.push({ type: match[1].trim().toUpperCase(), table: match[2], alias: match[3] && !SQL_KEYWORDS.has(match[3].toLowerCase()) ? match[3] : null, condition: (match[4] || '').trim() })
  }
  return joins
}

function extractClause(sql, startPattern, endPatterns) {
  const regex = new RegExp(`${startPattern}\\s+(.+?)(?=\\s+(?:${endPatterns.join('|')})\\b|$)`, 'i')
  const match = normalizeSql(sql).match(regex)
  return match ? match[1].trim() : ''
}

function extractCtes(sql) {
  const normalized = normalizeSql(sql)
  if (!/^with\b/i.test(normalized)) return []
  const beforeSelect = normalized.match(/^with\s+(recursive\s+)?(.+?)\s+select\b/i)
  if (!beforeSelect) return []
  return [...beforeSelect[2].matchAll(/([a-zA-Z_][\w]*)\s+as\s*\(/gi)].map((item) => item[1])
}

function calculateRisk({ sql, columns, tables, joins, filters, ctes }) {
  const findings = []
  let score = 0
  if (!normalizeSql(sql)) return { score: 0, level: 'none', findings }

  if (columns.some((column) => column === '*') || /select\s+\*/i.test(sql)) {
    score += 20
    findings.push({ severity: 'medium', type: 'performance', message: 'Uso de SELECT * detectado. Prefira projeção explícita de colunas.' })
  }
  if (!filters && tables.length > 0) {
    score += 15
    findings.push({ severity: 'medium', type: 'performance', message: 'Consulta sem cláusula WHERE detectada.' })
  }
  for (const join of joins) {
    if (!join.condition && !/cross/i.test(join.type)) {
      score += 25
      findings.push({ severity: 'high', type: 'integridade', message: `JOIN sem condição ON detectado para ${join.table}.` })
    }
  }
  if (DESTRUCTIVE_PATTERNS.some((pattern) => pattern.test(sql))) {
    score += 40
    findings.push({ severity: 'critical', type: 'seguranca', message: 'Comando potencialmente destrutivo detectado. Este módulo não deve executar SQL.' })
  }
  const piiColumns = columns.filter((column) => PII_PATTERNS.some((pattern) => pattern.test(column)))
  if (piiColumns.length) {
    score += 20
    findings.push({ severity: 'high', type: 'lgpd', message: `Possível exposição de PII: ${piiColumns.join(', ')}.` })
  }
  if (ctes.length >= 3) {
    score += 10
    findings.push({ severity: 'low', type: 'manutenibilidade', message: 'Consulta com múltiplas CTEs. Recomenda-se documentação da intenção de cada etapa.' })
  }
  if (/over\s*\(/i.test(sql)) findings.push({ severity: 'info', type: 'analytics', message: 'Função de janela detectada. Validar partição e ordenação da métrica.' })

  const boundedScore = Math.min(100, score)
  const level = boundedScore >= 75 ? 'critical' : boundedScore >= 50 ? 'high' : boundedScore >= 25 ? 'medium' : 'low'
  return { score: boundedScore, level, findings }
}

function buildGraph({ tables, joins, filters, orderBy, groupBy, ctes }) {
  const nodes = []
  const edges = []
  ctes.forEach((cte) => nodes.push({ id: `cte:${cte}`, label: cte, type: 'cte' }))
  tables.forEach(({ table, alias }) => nodes.push({ id: `table:${alias || table}`, label: alias ? `${table} (${alias})` : table, type: 'table' }))
  if (filters) nodes.push({ id: 'clause:where', label: 'WHERE', type: 'filter', detail: filters })
  if (groupBy) nodes.push({ id: 'clause:group', label: 'GROUP BY', type: 'aggregate', detail: groupBy })
  if (orderBy) nodes.push({ id: 'clause:order', label: 'ORDER BY', type: 'order', detail: orderBy })
  joins.forEach((join, index) => {
    const joinId = `join:${index}`
    nodes.push({ id: joinId, label: join.type, type: 'join', detail: join.condition || 'Sem condição detectada' })
    edges.push({ from: `table:${join.alias || join.table}`, to: joinId, label: join.condition || 'join' })
  })
  if (tables[0] && filters) edges.push({ from: `table:${tables[0].alias || tables[0].table}`, to: 'clause:where', label: 'filtra' })
  if (filters && groupBy) edges.push({ from: 'clause:where', to: 'clause:group', label: 'agrega' })
  if ((groupBy || filters || tables[0]) && orderBy) edges.push({ from: groupBy ? 'clause:group' : filters ? 'clause:where' : `table:${tables[0].alias || tables[0].table}`, to: 'clause:order', label: 'ordena' })
  return { nodes, edges }
}

function summarize({ tables, joins, filters, groupBy, orderBy, ctes }) {
  if (!tables.length && !ctes.length) return 'Informe uma consulta SELECT para gerar a intenção lógica.'
  const partes = []
  if (ctes.length) partes.push(`usa ${ctes.length} CTE(s) como etapa(s) intermediária(s)`)
  if (tables.length) partes.push(`consulta dados de ${tables.map((item) => item.table).join(', ')}`)
  if (joins.length) partes.push(`relaciona ${joins.length} junção(ões)`)
  if (filters) partes.push('aplica filtros de negócio')
  if (groupBy) partes.push('agrega resultados')
  if (orderBy) partes.push('ordena a saída')
  return `${partes.join(', ')}.`
}

export function analyzeSql(sql) {
  const normalized = normalizeSql(sql)
  const columns = splitSelectColumns(normalized)
  const tables = extractTables(normalized)
  const joins = extractJoins(normalized)
  const filters = extractClause(normalized, 'where', ['group\\s+by', 'order\\s+by', 'having', 'limit', 'offset'])
  const groupBy = extractClause(normalized, 'group\\s+by', ['order\\s+by', 'having', 'limit', 'offset'])
  const orderBy = extractClause(normalized, 'order\\s+by', ['limit', 'offset'])
  const ctes = extractCtes(normalized)
  const risk = calculateRisk({ sql: normalized, columns, tables, joins, filters, ctes })
  const graph = buildGraph({ tables, joins, filters, orderBy, groupBy, ctes })
  return { normalizedSql: normalized, summary: summarize({ tables, joins, filters, groupBy, orderBy, ctes }), columns, tables, joins, filters, groupBy, orderBy, ctes, riskScore: risk.score, riskLevel: risk.level, findings: risk.findings, graph }
}
