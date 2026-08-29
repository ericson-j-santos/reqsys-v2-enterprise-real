import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url))
const SOURCE_ROOT = path.resolve(SCRIPT_DIR, '..', 'src')

const REPLACEMENTS = [
  [/\bReqSys Teams policy readiness\b/giu, 'prontidão das políticas do Teams no ReqSys'],
  [/\bmerge readiness\b/giu, 'prontidão para integração'],
  [/\bcorrelation analytics\b/giu, 'indicadores de correlação'],
  [/\bGitHub ALM\b/giu, 'ciclo de entrega no GitHub'],
  [/\bpipeline ALM\b/giu, 'fluxo do ciclo de entrega'],
  [/\bHub Low-Code API\b/giu, 'Central de automações'],
  [/\bHub Low-Code\b/giu, 'Central de automações'],
  [/\bGraph API\b/giu, 'Microsoft Graph'],
  [/\bscore pós-correção\b/giu, 'nota após correção'],
  [/\bscore de governança\b/giu, 'nota de governança'],
  [/\bscore atual\b/giu, 'nota atual'],
  [/\bstatus geral\b/giu, 'situação geral'],
  [/\bhistórico merge readiness\b/giu, 'histórico de prontidão para integração'],
  [/\bmerge estabilizado\b/giu, 'integração estabilizada'],
  [/\bExecutor ALM\b/giu, 'Executor do ciclo de entrega'],
  [/\bCoordenação Geral de ADRs\b/giu, 'Coordenação geral de decisões de arquitetura'],
  [/\bHTTP POST URL do trigger\b/giu, 'endereço de chamada HTTP POST'],
  [/\bGuard rails\b/giu, 'proteções'],
  [/\bguard rail\b/giu, 'proteção'],
  [/\bguard rails\b/giu, 'proteções'],
  [/\brate limiting\b/giu, 'limitação de requisições'],
  [/\brate limit\b/giu, 'limite de requisições'],
  [/\bcorrelation[_ -]?id\b/giu, 'identificador de correlação'],
  [/\bPayload ReqSys\b/giu, 'Conteúdo da requisição ReqSys'],
  [/\bCI\/CD\b/gu, 'integração e publicação automáticas'],
  [/\bwork items\b/giu, 'itens de trabalho'],
  [/\bwork item\b/giu, 'item de trabalho'],
  [/\bdry[- ]run\b/giu, 'simulação'],
  [/\breadiness\b/giu, 'prontidão'],
  [/\blaunchpad\b/giu, 'central de ações'],
  [/\bdashboard\b/giu, 'painel'],
  [/\banalytics\b/giu, 'indicadores'],
  [/\bruntime\b/giu, 'execução'],
  [/\bpipeline\b/giu, 'fluxo'],
  [/\bworkspace\b/giu, 'área de trabalho'],
  [/\bshowcase\b/giu, 'demonstração'],
  [/\blogin\b/giu, 'acesso'],
  [/\bdeployments\b/giu, 'implantações'],
  [/\bdeployment\b/giu, 'implantação'],
  [/\bdeploy\b/giu, 'implantação'],
  [/\bworkflows\b/giu, 'fluxos de trabalho'],
  [/\bworkflow\b/giu, 'fluxo de trabalho'],
  [/\bstakeholders\b/giu, 'partes interessadas'],
  [/\bstakeholder\b/giu, 'parte interessada'],
  [/\bfeedback\b/giu, 'retorno'],
  [/\broadmaps\b/giu, 'planos de evolução'],
  [/\broadmap\b/giu, 'plano de evolução'],
  [/\bcompliance\b/giu, 'conformidade'],
  [/\bonboarding\b/giu, 'integração inicial'],
  [/\bartifacts\b/giu, 'artefatos'],
  [/\bartifact\b/giu, 'artefato'],
  [/\bfallback\b/giu, 'contingência'],
  [/\btriggers\b/giu, 'disparos'],
  [/\btrigger\b/giu, 'disparo'],
  [/\bhealth\b/giu, 'estado operacional'],
  [/\bcards\b/giu, 'cartões'],
  [/\bcard\b/giu, 'cartão'],
  [/\breleases\b/giu, 'publicações'],
  [/\brelease\b/giu, 'publicação'],
  [/\blogs\b/giu, 'registros'],
  [/\blog\b/giu, 'registro'],
  [/\bendpoints\b/giu, 'pontos de integração'],
  [/\bendpoint\b/giu, 'ponto de integração'],
  [/\bpayloads\b/giu, 'conteúdos das requisições'],
  [/\bpayload\b/giu, 'conteúdo da requisição'],
  [/\bretries\b/giu, 'novas tentativas'],
  [/\bretry\b/giu, 'nova tentativa'],
  [/\bbatches\b/giu, 'lotes'],
  [/\bbatch\b/giu, 'lote'],
  [/\bjobs\b/giu, 'tarefas'],
  [/\bjob\b/giu, 'tarefa'],
  [/\btimeouts\b/giu, 'tempos limite'],
  [/\btimeout\b/giu, 'tempo limite'],
  [/\brollbacks\b/giu, 'reversões'],
  [/\brollback\b/giu, 'reversão'],
  [/\bsmoke\b/giu, 'verificação rápida'],
  [/\bwebhooks\b/giu, 'chamadas automáticas'],
  [/\bwebhook\b/giu, 'chamada automática'],
  [/\bpreview\b/giu, 'prévia'],
  [/\bqueues\b/giu, 'filas'],
  [/\bqueue\b/giu, 'fila'],
  [/\bworkers\b/giu, 'processadores'],
  [/\bworker\b/giu, 'processador'],
  [/\blow[- ]code\b/giu, 'automações'],
  [/\bbackend\b/giu, 'serviço'],
  [/\bfrontend\b/giu, 'aplicação'],
  [/\bcache\b/giu, 'armazenamento temporário'],
  [/\bmock\b/giu, 'simulação'],
  [/\bfeatures\b/giu, 'funcionalidades'],
  [/\bfeature\b/giu, 'funcionalidade'],
  [/\bspecs\b/giu, 'especificações'],
  [/\bspec\b/giu, 'especificação'],
  [/\bgates\b/giu, 'verificações obrigatórias'],
  [/\bgate\b/giu, 'verificação obrigatória'],
  [/\bbranches\b/giu, 'versões de código'],
  [/\bbranch\b/giu, 'versão de código'],
  [/\bmerge\b/giu, 'integração de alterações'],
  [/\bstatus\b/giu, 'situação'],
  [/\bscore\b/giu, 'nota'],
  [/\bPRs\b/gu, 'solicitações de integração'],
  [/\bPR\b/gu, 'solicitação de integração'],
  [/\bCI\b/gu, 'verificações automáticas'],
  [/\bAPI\b/gu, 'serviço'],
  [/\bURL\b/gu, 'endereço'],
  [/\bLLM\b/gu, 'modelo de IA'],
  [/\bJWT\b/gu, 'token de acesso'],
  [/\bPII\b/gu, 'dados pessoais'],
  [/\bSDD\b/gu, 'especificação da solução'],
  [/\bALM\b/gu, 'administração do ciclo de entrega'],
  [/\bADRs\b/gu, 'decisões de arquitetura'],
  [/\bADR\b/gu, 'decisão de arquitetura'],
  [/\bDEV\b/gu, 'desenvolvimento'],
  [/\bSTG\b/gu, 'homologação'],
  [/\bPROD\b/gu, 'produção'],
  [/\bOnline\b/gu, 'Disponível'],
  [/\bOffline\b/gu, 'Indisponível'],
]

const USER_FACING_NAME = '(?:erro|error|mensagem|message|aviso|alerta|sucesso|descricao|description|titulo|title|rotulo|label|placeholder)'
const JS_PROPERTY = /\b(title|titulo|tip|topic|rotulo|label|message|mensagem|placeholder|description|descricao)(\s*:\s*)(['"`])([\s\S]*?)\3/g
const JS_ASSIGNMENT = new RegExp(`\\b(${USER_FACING_NAME})(\\.value)?(\\s*=\\s*)(['"\`])([\\s\\S]*?)\\4`, 'g')
const JS_FALLBACK = new RegExp(`(\\b${USER_FACING_NAME}(?:\\.value)?\\s*=\\s*[^\\n;]*?\\|\\|\\s*)(['"\`])([^\\n]*?)\\2`, 'g')
const STRING_LITERAL = /(['"`])((?:\\.|(?!\1)[\s\S])*?)\1/g
const VISIBLE_HTML_ATTR = /\b(aria-label|title|subtitle|placeholder|label|text|hint|chip-tooltip|empty-text|no-data-text|alt|caption)=(['"])(.*?)\2/giu

function preserveInitialCase(match, replacement) {
  const first = match.match(/[A-Za-zÀ-ÿ]/u)?.[0]
  if (!first || first !== first.toUpperCase() || first === first.toLowerCase()) return replacement
  return replacement.charAt(0).toUpperCase() + replacement.slice(1)
}

function replaceHumanText(value) {
  let output = value
  for (const [pattern, replacement] of REPLACEMENTS) {
    pattern.lastIndex = 0
    output = output.replace(pattern, (match) => preserveInitialCase(match, replacement))
  }
  return output
}

function maskPreservingLines(text, regex) {
  return text.replace(regex, (block) => block.replace(/[^\n]/g, ' '))
}

function findRootBlock(content, tagName) {
  const withoutComments = maskPreservingLines(content, /<!--[\s\S]*?-->/g)
  const tagRegex = new RegExp(`<\\/?${tagName}\\b[^>]*>`, 'giu')
  let depth = 0
  let openStart = -1
  let innerStart = -1
  let match
  while ((match = tagRegex.exec(withoutComments))) {
    const closing = match[0].startsWith('</')
    if (!closing) {
      if (depth === 0) {
        openStart = match.index
        innerStart = tagRegex.lastIndex
      }
      depth += 1
      continue
    }
    if (depth === 0) continue
    depth -= 1
    if (depth === 0) return { openStart, innerStart, innerEnd: match.index, closeEnd: tagRegex.lastIndex }
  }
  return null
}

function isLikelyHumanLiteral(value) {
  const text = String(value).replace(/\s+/g, ' ').trim()
  if (!text) return false
  if (/^(?:https?:\/\/|\/|\.\/|\.\.\/)/i.test(text)) return false
  if (/^[a-z][a-z0-9_.:/-]*$/u.test(text)) return false
  if (/^[A-Z0-9_]+$/u.test(text)) return false
  if (/^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+$/u.test(text)) return false
  if (/^[a-z0-9_.:/-]*\$\{[^}]+\}[a-z0-9_.:/-]*$/i.test(text)) return false
  return /\s|[À-ÿ]|[.!?,;:()]/u.test(text) || /^[A-Z][a-zÀ-ÿ]+$/u.test(text)
}

function replaceHumanScriptLiterals(content) {
  return content.replace(STRING_LITERAL, (full, quote, value) => {
    if (!isLikelyHumanLiteral(value)) return full
    const replaced = replaceHumanText(value)
    return `${quote}${replaced}${quote}`
  })
}

function transformJavascript(content) {
  let result = content.replace(JS_PROPERTY, (full, name, separator, quote, value) => `${name}${separator}${quote}${replaceHumanText(value)}${quote}`)
  result = result.replace(JS_ASSIGNMENT, (full, name, valueSuffix = '', separator, quote, value) => `${name}${valueSuffix || ''}${separator}${quote}${replaceHumanText(value)}${quote}`)
  result = result.replace(JS_FALLBACK, (full, prefix, quote, value) => `${prefix}${quote}${replaceHumanText(value)}${quote}`)
  return replaceHumanScriptLiterals(result)
}

function transformInterpolation(expression) {
  return expression.replace(STRING_LITERAL, (full, quote, value) => `${quote}${replaceHumanText(value)}${quote}`)
}

function transformTextNode(value) {
  return value.split(/({{[\s\S]*?}})/g).map((part) => {
    if (part.startsWith('{{') && part.endsWith('}}')) return `{{${transformInterpolation(part.slice(2, -2))}}}`
    return replaceHumanText(part)
  }).join('')
}

function protectTemplateBlocks(template) {
  const blocks = []
  const protectedTemplate = template
    .replace(/<(?:code|pre)\b[^>]*>[\s\S]*?<\/(?:code|pre)>/giu, (block) => {
      const token = `__REQSYS_LANG_BLOCK_${blocks.length}__`
      blocks.push(block)
      return token
    })
    .replace(/<!--[\s\S]*?-->/g, (block) => {
      const token = `__REQSYS_LANG_BLOCK_${blocks.length}__`
      blocks.push(block)
      return token
    })
  return { protectedTemplate, blocks }
}

function transformTemplate(template) {
  const { protectedTemplate, blocks } = protectTemplateBlocks(template)
  let result = protectedTemplate.replace(/>([^<]+)</g, (full, value) => `>${transformTextNode(value)}<`)
  result = result.replace(VISIBLE_HTML_ATTR, (full, name, quote, value) => `${name}=${quote}${replaceHumanText(value)}${quote}`)
  return result.replace(/__REQSYS_LANG_BLOCK_(\d+)__/g, (_, index) => blocks[Number(index)])
}

function replaceBlockInner(content, block, transformer) {
  if (!block) return content
  const before = content.slice(0, block.innerStart)
  const inner = content.slice(block.innerStart, block.innerEnd)
  const after = content.slice(block.innerEnd)
  return `${before}${transformer(inner)}${after}`
}

function transformVue(content) {
  const templateBlock = findRootBlock(content, 'template')
  let output = replaceBlockInner(content, templateBlock, transformTemplate)
  const scriptBlock = findRootBlock(output, 'script')
  output = replaceBlockInner(output, scriptBlock, transformJavascript)
  return output
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

let changedFiles = 0
for (const filePath of walk(SOURCE_ROOT)) {
  const before = fs.readFileSync(filePath, 'utf8')
  const after = path.extname(filePath).toLowerCase() === '.vue' ? transformVue(before) : transformJavascript(before)
  if (after === before) continue
  fs.writeFileSync(filePath, after, 'utf8')
  changedFiles += 1
  console.log(`corrigido: ${path.relative(path.resolve(SOURCE_ROOT, '..'), filePath)}`)
}
console.log(`Arquivos corrigidos: ${changedFiles}`)
