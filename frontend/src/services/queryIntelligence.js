const SQL_KEYWORDS = new Set(['select', 'from', 'where', 'join', 'inner', 'left', 'right', 'full', 'outer', 'cross', 'on', 'group', 'by', 'order', 'having', 'limit', 'offset', 'with', 'recursive', 'union', 'all', 'distinct', 'case', 'when', 'then', 'else', 'end', 'as', 'and', 'or'])

const PERSONAL_DATA_PATTERNS = [/\bcpf\b/i, /\bcnpj\b/i, /\bemail\b/i, /\btelefone\b/i, /\bcelular\b/i, /\bnome\b/i, /\bendereco\b/i, /\bconta\b/i, /\bagencia\b/i]
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
    joins.push({
      type: match[1].trim().toUpperCase(),
      table: match[2],
      alias: match[3] && !SQL_KEYWORDS.has(match[3].toLowerCase()) ? match[3] : null,
      condition: (match[4] || '').trim(),
    })
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

  const cteBody = normalized.replace(/^with\s+(recursive\s+)?/i, '')
  const ctes = []
  let depth = 0
  let index = 0

  while (index < cteBody.length) {
    const remaining = cteBody.slice(index)
    if (depth === 0 && /^\s*select\b/i.test(remaining)) break

    if (depth === 0) {
      const cteMatch = remaining.match(/^\s*([a-zA-Z_][\w]*)\s+as\s*\(/i)
      if (cteMatch) {
        ctes.push(cteMatch[1])
        index += cteMatch[0].length - 1
        continue
      }
    }

    const char = cteBody[index]
    if (char === '(') depth += 1
    if (char === ')') depth = Math.max(0, depth - 1)
    index += 1
  }

  return [...new Set(ctes)]
}

function calculateRisk({ sql, columns, tables, joins, filters, ctes }) {
  const findings = []
  let value = 0
  if (!normalizeSql(sql)) return { value: 0, level: 'none', findings }

  if (columns.some((column) => column === '*') || /select\s+\*/i.test(sql)) {
    value += 20
    findings.push({ severity: 'medium', type: 'desempenho', message: 'Uso de SELECT * detectado. Prefira informar as colunas necessárias.' })
  }
  if (!filters && tables.length > 0) {
    value += 15
    findings.push({ severity: 'medium', type: 'desempenho', message: 'Consulta sem cláusula WHERE detectada.' })
  }
  for (const join of joins) {
    if (!join.condition && !/cross/i.test(join.type)) {
      value += 25
      findings.push({ severity: 'high', type: 'integridade', message: `JOIN sem condição ON detectado para ${join.table}.` })
    }
  }
  if (DESTRUCTIVE_PATTERNS.some((pattern) => pattern.test(sql))) {
    value += 40
    findings.push({ severity: 'critical', type: 'seguranca', message: 'Comando potencialmente destrutivo detectado. A análise não executa SQL.' })
  }
  const personalDataColumns = columns.filter((column) => PERSONAL_DATA_PATTERNS.some((pattern) => pattern.test(column)))
  if (personalDataColumns.length) {
    value += 20
    findings.push({ severity: 'high', type: 'dados-pessoais', message: `Possível exposição de dados pessoais: ${personalDataColumns.join(', ')}.` })
  }
  if (ctes.length >= 3) {
    value += 10
    findings.push({ severity: 'low', type: 'manutenibilidade', message: 'Consulta com várias CTEs. Documente a intenção de cada etapa.' })
  }
  if (/over\s*\(/i.test(sql)) {
    findings.push({ severity: 'info', type: 'analise', message: 'Função de janela detectada. Verifique a partição e a ordenação da métrica.' })
  }

  const bounded = Math.min(100, value)
  const level = bounded >= 75 ? 'critical' : bounded >= 50 ? 'high' : bounded >= 25 ? 'medium' : 'low'
  return { value: bounded, level, findings }
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
  if ((groupBy || filters || tables[0]) && orderBy) {
    edges.push({ from: groupBy ? 'clause:group' : filters ? 'clause:where' : `table:${tables[0].alias || tables[0].table}`, to: 'clause:order', label: 'ordena' })
  }
  return { nodes, edges }
}

function summarize({ tables, joins, filters, groupBy, orderBy, ctes }) {
  if (!tables.length && !ctes.length) return 'Informe uma consulta SELECT para gerar a intenção lógica.'
  const parts = []
  if (ctes.length) parts.push(`usa ${ctes.length} CTE(s) como etapa(s) intermediária(s)`)
  if (tables.length) parts.push(`consulta dados de ${tables.map((item) => item.table).join(', ')}`)
  if (joins.length) parts.push(`relaciona ${joins.length} junção(ões)`)
  if (filters) parts.push('aplica filtros de negócio')
  if (groupBy) parts.push('agrega resultados')
  if (orderBy) parts.push('ordena a saída')
  return `${parts.join(', ')}.`
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

  return {
    normalizedSql: normalized,
    summary: summarize({ tables, joins, filters, groupBy, orderBy, ctes }),
    columns,
    tables,
    joins,
    filters,
    groupBy,
    orderBy,
    ctes,
    riskScore: risk.value,
    riskLevel: risk.level,
    findings: risk.findings,
    graph,
  }
}
