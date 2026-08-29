import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url))
export const FRONTEND_ROOT = path.resolve(SCRIPT_DIR, '..')
export const SOURCE_ROOT = path.join(FRONTEND_ROOT, 'src')

export const FORBIDDEN_TERMS = [
  { id: 'runtime', pattern: /\bruntime\b/giu, suggestion: 'execução' },
  { id: 'dashboard', pattern: /\bdashboard\b/giu, suggestion: 'painel' },
  { id: 'work-item', pattern: /\bwork\s+items?\b/giu, suggestion: 'item de trabalho' },
  { id: 'launchpad', pattern: /\blaunchpad\b/giu, suggestion: 'ações / central de ações' },
  { id: 'branch', pattern: /\bbranch(?:es)?\b/giu, suggestion: 'versão de código / ramificação' },
  { id: 'merge', pattern: /\bmerge\b/giu, suggestion: 'integração de alterações' },
  { id: 'dry-run', pattern: /\bdry[- ]run\b/giu, suggestion: 'simulação' },
  { id: 'readiness', pattern: /\breadiness\b/giu, suggestion: 'prontidão' },
  { id: 'score', pattern: /\bscore\b/giu, suggestion: 'nota / índice' },
  { id: 'analytics', pattern: /\banalytics\b/giu, suggestion: 'indicadores / análise' },
  { id: 'low-code', pattern: /\blow[- ]code\b/giu, suggestion: 'automações' },
  { id: 'status', pattern: /\bstatus\b/giu, suggestion: 'situação' },
  { id: 'cache', pattern: /\bcache\b/giu, suggestion: 'armazenamento temporário' },
  { id: 'mock', pattern: /\bmock\b/giu, suggestion: 'simulação' },
  { id: 'specs', pattern: /\bspecs?\b/giu, suggestion: 'especificações' },
  { id: 'feature', pattern: /\bfeatures?\b/giu, suggestion: 'funcionalidade' },
  { id: 'gate', pattern: /\bgates?\b/giu, suggestion: 'verificação obrigatória' },
  { id: 'backend', pattern: /\bback[- ]?end\b/giu, suggestion: 'serviço' },
  { id: 'frontend', pattern: /\bfront[- ]?end\b/giu, suggestion: 'aplicação / interface' },
  { id: 'pipeline', pattern: /\bpipeline\b/giu, suggestion: 'fluxo' },
  { id: 'workspace', pattern: /\bworkspace\b/giu, suggestion: 'área de trabalho' },
  { id: 'showcase', pattern: /\bshowcase\b/giu, suggestion: 'demonstração' },
  { id: 'login', pattern: /\blogin\b/giu, suggestion: 'entrar / acesso' },
  { id: 'deploy', pattern: /\bdeploy(?:ment)?s?\b/giu, suggestion: 'implantação / publicação' },
  { id: 'workflow', pattern: /\bworkflows?\b/giu, suggestion: 'fluxo de trabalho' },
  { id: 'stakeholder', pattern: /\bstakeholders?\b/giu, suggestion: 'parte interessada' },
  { id: 'feedback', pattern: /\bfeedback\b/giu, suggestion: 'retorno' },
  { id: 'roadmap', pattern: /\broadmaps?\b/giu, suggestion: 'plano de evolução' },
  { id: 'compliance', pattern: /\bcompliance\b/giu, suggestion: 'conformidade' },
  { id: 'onboarding', pattern: /\bonboarding\b/giu, suggestion: 'integração inicial' },
  { id: 'artifact', pattern: /\bartifacts?\b/giu, suggestion: 'artefato' },
  { id: 'fallback', pattern: /\bfallback\b/giu, suggestion: 'alternativa / contingência' },
  { id: 'trigger', pattern: /\btriggers?\b/giu, suggestion: 'disparo' },
  { id: 'health', pattern: /\bhealth\b/giu, suggestion: 'saúde / estado operacional' },
  { id: 'card', pattern: /\bcards?\b/giu, suggestion: 'cartão' },
  { id: 'release', pattern: /\breleases?\b/giu, suggestion: 'publicação / versão liberada' },
  { id: 'logs', pattern: /\blogs?\b/giu, suggestion: 'registros' },
  { id: 'endpoint', pattern: /\bendpoints?\b/giu, suggestion: 'endereço / ponto de integração' },
  { id: 'payload', pattern: /\bpayloads?\b/giu, suggestion: 'conteúdo da requisição' },
  { id: 'retry', pattern: /\bretr(?:y|ies)\b/giu, suggestion: 'nova tentativa' },
  { id: 'batch', pattern: /\bbatches?\b/giu, suggestion: 'lote' },
  { id: 'job', pattern: /\bjobs?\b/giu, suggestion: 'tarefa' },
  { id: 'timeout', pattern: /\btimeouts?\b/giu, suggestion: 'tempo limite' },
  { id: 'rollback', pattern: /\brollbacks?\b/giu, suggestion: 'reversão' },
  { id: 'smoke', pattern: /\bsmoke\b/giu, suggestion: 'verificação rápida' },
  { id: 'webhook', pattern: /\bwebhooks?\b/giu, suggestion: 'chamada automática' },
  { id: 'preview', pattern: /\bpreview\b/giu, suggestion: 'prévia' },
  { id: 'queue', pattern: /\bqueues?\b/giu, suggestion: 'fila' },
  { id: 'worker', pattern: /\bworkers?\b/giu, suggestion: 'processador' },
  { id: 'ci-cd', pattern: /\bCI\s*\/\s*CD\b/gu, suggestion: 'integração e publicação automáticas' },
  { id: 'ci', pattern: /\bCI\b/gu, suggestion: 'verificações automáticas' },
  { id: 'pr', pattern: /\bPRs?\b/gu, suggestion: 'solicitação de integração' },
  { id: 'api', pattern: /\bAPI\b/gu, suggestion: 'serviço / integração' },
  { id: 'url', pattern: /\bURL\b/gu, suggestion: 'endereço' },
  { id: 'llm', pattern: /\bLLM\b/gu, suggestion: 'modelo de IA' },
  { id: 'pii', pattern: /\bPII\b/gu, suggestion: 'dados pessoais' },
  { id: 'sdd', pattern: /\bSDD\b/gu, suggestion: 'especificação da solução' },
  { id: 'alm', pattern: /\bALM\b/gu, suggestion: 'administração do ciclo de entrega' },
  { id: 'adr', pattern: /\bADRs?\b/gu, suggestion: 'decisão de arquitetura' },
  { id: 'dev', pattern: /\bDEV\b/gu, suggestion: 'desenvolvimento' },
  { id: 'stg', pattern: /\bSTG\b/gu, suggestion: 'homologação' },
  { id: 'prod', pattern: /\bPROD\b/gu, suggestion: 'produção' },
]

const USER_FACING_NAME = '(?:erro|error|mensagem|message|aviso|alerta|sucesso|descricao|description|titulo|title|rotulo|label|placeholder)'
const USER_FACING_JS_PROPERTY = /\b(?:title|titulo|tip|topic|rotulo|label|message|mensagem|placeholder|description|descricao)\s*:\s*(['"`])([\s\S]*?)\1/g
const USER_FACING_ASSIGNMENT = new RegExp(`\\b${USER_FACING_NAME}(?:\\.value)?\\s*=\\s*(['"\`])([\\s\\S]*?)\\1`, 'g')
const USER_FACING_FALLBACK = new RegExp(`\\b${USER_FACING_NAME}(?:\\.value)?\\s*=\\s*[^\\n;]*?\\|\\|\\s*(['"\`])([^\\n]*?)\\1`, 'g')
const SELECTED_HTML_ATTR = /\b(?:aria-label|title|placeholder)\s*=\s*(['"])(.*?)\1/giu
const QUOTED_LITERAL = /(['"`])((?:\\.|(?!\1)[\s\S])*?)\1/g

function lineFromOffset(text, offset) { return text.slice(0, offset).split('\n').length }
function normalizeCandidate(value) { return String(value).replace(/\\n/g, ' ').replace(/\s+/g, ' ').trim() }

function isRelevantCandidate(value) {
  const text = normalizeCandidate(value)
  if (!text) return false
  if (/^(?:https?:\/\/|\/|\.\/|\.\.\/)/i.test(text)) return false
  if (/^[a-z0-9_.:/-]+$/i.test(text) && !/\s/.test(text) && text === text.toLowerCase()) return false
  if (/^[a-z0-9_.:/-]*\$\{[^}]+\}[a-z0-9_.:/-]*$/i.test(text)) return false
  if (/^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+$/u.test(text)) return false
  return /[A-Za-zÀ-ÿ]/u.test(text)
}

function maskMachineTokens(text) { return text.replace(/\b[a-z0-9]+(?:[-_.:/][a-z0-9]+){2,}\b/g, ' ') }
function maskPreservingLines(text, regex) { return text.replace(regex, (block) => block.replace(/[^\n]/g, ' ')) }

export function findForbiddenTerms(text) {
  const normalized = maskMachineTokens(normalizeCandidate(text))
  const hits = []
  for (const rule of FORBIDDEN_TERMS) {
    rule.pattern.lastIndex = 0
    if (rule.pattern.test(normalized)) hits.push({ id: rule.id, suggestion: rule.suggestion })
  }
  return hits
}

function collectTemplateCandidates(content) {
  const result = []
  const templateMatch = /<template\b[^>]*>([\s\S]*?)<\/template>/i.exec(content)
  if (!templateMatch) return result
  const template = templateMatch[1]
  const templateOffset = templateMatch.index + templateMatch[0].indexOf(template)
  const withoutExecutableBlocks = maskPreservingLines(template, /<(?:code|pre)\b[^>]*>[\s\S]*?<\/(?:code|pre)>/giu)
  const withoutComments = maskPreservingLines(withoutExecutableBlocks, /<!--[\s\S]*?-->/g)

  let attrMatch
  SELECTED_HTML_ATTR.lastIndex = 0
  while ((attrMatch = SELECTED_HTML_ATTR.exec(withoutComments))) result.push({ text: attrMatch[2], line: lineFromOffset(content, templateOffset + attrMatch.index), origin: 'atributo visível' })

  const textNodeRegex = />([^<]+)</g
  let textMatch
  while ((textMatch = textNodeRegex.exec(withoutComments))) {
    const raw = textMatch[1]
    const interpolationFree = raw.replace(/{{[\s\S]*?}}/g, ' ')
    if (isRelevantCandidate(interpolationFree)) result.push({ text: interpolationFree, line: lineFromOffset(content, templateOffset + textMatch.index), origin: 'texto da tela' })
    const interpolationRegex = /{{([\s\S]*?)}}/g
    let interpolationMatch
    while ((interpolationMatch = interpolationRegex.exec(raw))) {
      QUOTED_LITERAL.lastIndex = 0
      let literalMatch
      while ((literalMatch = QUOTED_LITERAL.exec(interpolationMatch[1]))) {
        if (isRelevantCandidate(literalMatch[2])) result.push({ text: literalMatch[2], line: lineFromOffset(content, templateOffset + textMatch.index), origin: 'texto condicional da tela' })
      }
    }
  }
  return result
}

function collectRegexCandidates(content, regex, origin) {
  const result = []
  regex.lastIndex = 0
  let match
  while ((match = regex.exec(content))) {
    if (isRelevantCandidate(match[2])) result.push({ text: match[2], line: lineFromOffset(content, match.index), origin })
  }
  return result
}

function collectJavascriptCandidates(content) {
  return [
    ...collectRegexCandidates(content, USER_FACING_JS_PROPERTY, 'propriedade de interface'),
    ...collectRegexCandidates(content, USER_FACING_ASSIGNMENT, 'mensagem de interface'),
    ...collectRegexCandidates(content, USER_FACING_FALLBACK, 'mensagem alternativa de interface'),
  ]
}

export function findViolationsInFile(filePath, content) {
  const extension = path.extname(filePath).toLowerCase()
  const candidates = extension === '.vue' ? [...collectTemplateCandidates(content), ...collectJavascriptCandidates(content)] : collectJavascriptCandidates(content)
  const violations = []
  const seen = new Set()
  for (const candidate of candidates) {
    for (const hit of findForbiddenTerms(candidate.text)) {
      const key = `${candidate.line}:${hit.id}:${normalizeCandidate(candidate.text)}`
      if (seen.has(key)) continue
      seen.add(key)
      violations.push({ filePath, line: candidate.line, origin: candidate.origin, text: normalizeCandidate(candidate.text), term: hit.id, suggestion: hit.suggestion })
    }
  }
  return violations
}

function walk(directory) {
  const files = []
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name)
    if (entry.isDirectory()) {
      if (['node_modules', 'dist', 'coverage', 'test', '__tests__'].includes(entry.name)) continue
      files.push(...walk(fullPath))
      continue
    }
    if (!/\.(?:vue|js|ts)$/i.test(entry.name)) continue
    if (/\.(?:spec|test)\.[^.]+$/i.test(entry.name)) continue
    files.push(fullPath)
  }
  return files
}

export function validateRepository(sourceRoot = SOURCE_ROOT) {
  const violations = []
  for (const filePath of walk(sourceRoot)) violations.push(...findViolationsInFile(filePath, fs.readFileSync(filePath, 'utf8')))
  return violations
}

function runCli() {
  const violations = validateRepository()
  if (!violations.length) {
    console.log('Linguagem simples: aprovado. Nenhum termo proibido foi encontrado nos textos estáticos e mensagens conhecidas da interface.')
    return
  }
  console.error(`Linguagem simples: ${violations.length} ocorrência(s) proibida(s) encontrada(s).`)
  for (const violation of violations) {
    const relative = path.relative(path.resolve(FRONTEND_ROOT, '..'), violation.filePath)
    console.error(`- ${relative}:${violation.line} [${violation.term}] ${violation.origin}: "${violation.text}" → usar ${violation.suggestion}`)
  }
  process.exitCode = 1
}

const invokedAsScript = process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href
if (invokedAsScript) runCli()
