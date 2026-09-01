import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url))
const SOURCE_ROOT = path.resolve(SCRIPT_DIR, '..', 'src')

const REPLACEMENTS = [
  [/\bReqSys Teams policy readiness\b/giu, 'Prontidão das políticas do Teams no ReqSys'],
  [/\bMerge readiness\b/gu, 'Prontidão para integração'],
  [/\bmerge readiness\b/gu, 'prontidão para integração'],
  [/\bMergeável\b/gu, 'Pode ser integrado'],
  [/\bmergeável\b/gu, 'pode ser integrado'],
  [/\bCI vermelho\b/gu, 'verificações automáticas em falha'],
  [/\bGraph API\b/gu, 'Microsoft Graph'],
  [/\bHub Low-Code API\b/gu, 'Central de automações'],
  [/\bHub Low-Code\b/gu, 'Central de automações'],
  [/\bLow-Code\b/gu, 'Automações'],
  [/\blow-code\b/gu, 'automações'],
  [/\bSpecs SDD\b/gu, 'Especificações da solução'],
  [/\bADRs relacionados\b/gu, 'Decisões de arquitetura relacionadas'],
  [/\bADRs relacionadas\b/gu, 'Decisões de arquitetura relacionadas'],
  [/\bScore médio\b/gu, 'Nota média'],
  [/\bscore médio\b/gu, 'nota média'],
  [/\bScore alto\b/gu, 'Nota alta'],
  [/\bscore alto\b/gu, 'nota alta'],
  [/\bScore atual\b/gu, 'Nota atual'],
  [/\bscore atual\b/gu, 'nota atual'],
  [/\bScore pós-correção\b/gu, 'Nota após correção'],
  [/\bscore pós-correção\b/gu, 'nota após correção'],
  [/\bScore governado\b/gu, 'Nota controlada'],
  [/\bscore governado\b/gu, 'nota controlada'],
  [/\bScore não atualizado\b/gu, 'Nota não atualizada'],
  [/\bscore não atualizado\b/gu, 'nota não atualizada'],
  [/\bRuntime Operacional Navegável\b/gu, 'Execução operacional navegável'],
  [/\bRuntime operacional\b/gu, 'Execução operacional'],
  [/\bruntime operacional\b/gu, 'execução operacional'],
  [/\bCorrelation analytics\b/gu, 'Indicadores de correlação'],
  [/\bGitHub ALM\b/gu, 'ciclo de entrega no GitHub'],
  [/\bPipeline ALM\b/gu, 'Fluxo do ciclo de entrega'],
  [/\bCI\/CD\b/gu, 'integração e publicação automáticas'],
  [/\bWork items\b/gu, 'Itens de trabalho'],
  [/\bwork items\b/gu, 'itens de trabalho'],
  [/\bWork item\b/gu, 'Item de trabalho'],
  [/\bwork item\b/gu, 'item de trabalho'],
  [/\bDry-run\b/gu, 'Simulação'],
  [/\bdry-run\b/gu, 'simulação'],
  [/\bReadiness\b/gu, 'Prontidão'],
  [/\breadiness\b/gu, 'prontidão'],
  [/\bLaunchpad\b/gu, 'Central de ações'],
  [/\blaunchpad\b/gu, 'central de ações'],
  [/\bDashboard\b/gu, 'Painel'],
  [/\bdashboard\b/gu, 'painel'],
  [/\bAnalytics\b/gu, 'Indicadores'],
  [/\banalytics\b/gu, 'indicadores'],
  [/\bRuntime\b/gu, 'Execução'],
  [/\bruntime\b/gu, 'execução'],
  [/\bPipeline\b/gu, 'Fluxo'],
  [/\bpipeline\b/gu, 'fluxo'],
  [/\bWorkspace\b/gu, 'Área de trabalho'],
  [/\bworkspace\b/gu, 'área de trabalho'],
  [/\bShowcase\b/gu, 'Demonstração'],
  [/\bshowcase\b/gu, 'demonstração'],
  [/\bLogin\b/gu, 'Acesso'],
  [/\blogin\b/gu, 'acesso'],
  [/\bBackend\b/gu, 'Serviço'],
  [/\bbackend\b/gu, 'serviço'],
  [/\bFrontend\b/gu, 'Aplicação'],
  [/\bfrontend\b/gu, 'aplicação'],
  [/\bCache\b/gu, 'Armazenamento temporário'],
  [/\bcache\b/gu, 'armazenamento temporário'],
  [/\bMock\b/gu, 'Simulação'],
  [/\bmock\b/gu, 'simulação'],
  [/\bFeatures\b/gu, 'Funcionalidades'],
  [/\bfeatures\b/gu, 'funcionalidades'],
  [/\bFeature\b/gu, 'Funcionalidade'],
  [/\bfeature\b/gu, 'funcionalidade'],
  [/\bSpecs\b/gu, 'Especificações'],
  [/\bspecs\b/gu, 'especificações'],
  [/\bGates\b/gu, 'Verificações obrigatórias'],
  [/\bgates\b/gu, 'verificações obrigatórias'],
  [/\bGate\b/gu, 'Verificação obrigatória'],
  [/\bgate\b/gu, 'verificação obrigatória'],
  [/\bBranches\b/gu, 'Versões de código'],
  [/\bbranches\b/gu, 'versões de código'],
  [/\bBranch\b/gu, 'Versão de código'],
  [/\bbranch\b/gu, 'versão de código'],
  [/\bMerge\b/gu, 'Integração de alterações'],
  [/\bmerge\b/gu, 'integração de alterações'],
  [/\bStatus\b/gu, 'Situação'],
  [/\bstatus\b/gu, 'situação'],
  [/\bScore\b/gu, 'Nota'],
  [/\bscore\b/gu, 'nota'],
  [/\bPRs\b/gu, 'Solicitações de integração'],
  [/\bPR\b/gu, 'Solicitação de integração'],
  [/\bCI\b/gu, 'verificações automáticas'],
  [/\bAPI\b/gu, 'serviço'],
  [/\bURL\b/gu, 'endereço'],
  [/\bLLM\b/gu, 'modelo de IA'],
  [/\bPII\b/gu, 'dados pessoais'],
  [/\bSDD\b/gu, 'especificação da solução'],
  [/\bALM\b/gu, 'administração do ciclo de entrega'],
  [/\bADRs\b/gu, 'decisões de arquitetura'],
  [/\bADR\b/gu, 'decisão de arquitetura'],
  [/\bDEV\b/gu, 'desenvolvimento'],
  [/\bSTG\b/gu, 'homologação'],
  [/\bPROD\b/gu, 'produção'],
]

const USER_FACING_NAME = '(?:erro|error|mensagem|message|aviso|alerta|sucesso|descricao|description|titulo|title|rotulo|label|placeholder)'
const JS_PROPERTY = /\b(title|titulo|tip|topic|rotulo|label|message|mensagem|placeholder|description|descricao)(\s*:\s*)(['"`])([\s\S]*?)\3/g
const JS_ASSIGNMENT = new RegExp(`\\b(${USER_FACING_NAME})(\\.value)?(\\s*=\\s*)(['"\`])([\\s\\S]*?)\\4`, 'g')
const JS_FALLBACK = new RegExp(`(\\b${USER_FACING_NAME}(?:\\.value)?\\s*=\\s*[^\\n;]*?\\|\\|\\s*)(['"\`])([^\\n]*?)\\2`, 'g')
const STRING_LITERAL = /(['"`])((?:\\.|(?!\1)[^\\])*?)\1/g

function replaceHumanText(value) {
  let output = value
  for (const [pattern, replacement] of REPLACEMENTS) {
    pattern.lastIndex = 0
    output = output.replace(pattern, replacement)
  }
  return output
}

function isLikelyHumanLiteral(value) {
  const text = String(value).trim()
  if (!text) return false
  if (/^(?:https?:\/\/|\/|\.\/|\.\.\/)/i.test(text)) return false
  if (/^[a-z0-9_.:/-]+$/i.test(text) && text === text.toLowerCase()) return false
  if (/^[A-Z0-9_.:/-]+$/u.test(text) && !/\s/u.test(text)) return false
  if (/^[a-z0-9_.:/-]*\$\{[^}]+\}[a-z0-9_.:/-]*$/i.test(text)) return false
  // STRING_LITERAL não entende aninhamento de template literals (backtick):
  // um `${a}/rota${cond ? `?${b}` : ''}` é cortado no backtick interno e
  // sobra um "${" sem "}" correspondente — sinal de que isto não é o
  // conteúdo real de uma string, e sim um recorte indevido de código.
  const opens = (text.match(/\$\{/g) || []).length
  const closes = (text.match(/\}/g) || []).length
  if (opens !== closes) return false
  return /\s|[À-ÿ]|[.!?,;:()]/u.test(text) || /^[A-Z][a-zÀ-ÿ]+$/u.test(text)
}

function replaceQuotedHumanLiterals(content) {
  return content.replace(STRING_LITERAL, (full, quote, value) => {
    if (!isLikelyHumanLiteral(value)) return full
    const replaced = replaceHumanText(value)
    return replaced === value ? full : `${quote}${replaced}${quote}`
  })
}

function transformJavascript(content) {
  let result = content.replace(JS_PROPERTY, (full, name, separator, quote, value) => {
    return `${name}${separator}${quote}${replaceHumanText(value)}${quote}`
  })
  result = result.replace(JS_ASSIGNMENT, (full, name, valueSuffix = '', separator, quote, value) => {
    return `${name}${valueSuffix || ''}${separator}${quote}${replaceHumanText(value)}${quote}`
  })
  result = result.replace(JS_FALLBACK, (full, prefix, quote, value) => {
    return `${prefix}${quote}${replaceHumanText(value)}${quote}`
  })
  return replaceQuotedHumanLiterals(result)
}

function transformInterpolation(expression) {
  return expression.replace(STRING_LITERAL, (full, quote, value) => {
    const replaced = replaceHumanText(value)
    return replaced === value ? full : `${quote}${replaced}${quote}`
  })
}

function transformTextNode(value) {
  const parts = value.split(/({{[\s\S]*?}})/g)
  return parts.map((part) => {
    if (part.startsWith('{{') && part.endsWith('}}')) {
      return `{{${transformInterpolation(part.slice(2, -2))}}}`
    }
    return replaceHumanText(part)
  }).join('')
}

function protectBlocks(template) {
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

function restoreBlocks(template, blocks) {
  return template.replace(/__REQSYS_LANG_BLOCK_(\d+)__/g, (_, index) => blocks[Number(index)])
}

function transformTemplate(template) {
  const { protectedTemplate, blocks } = protectBlocks(template)
  let result = protectedTemplate.replace(/>([^<]+)</g, (full, value) => `>${transformTextNode(value)}<`)
  result = result.replace(/\b(aria-label|title|placeholder|label)=(['"])(.*?)\2/giu, (full, name, quote, value) => {
    return `${name}=${quote}${replaceHumanText(value)}${quote}`
  })
  return restoreBlocks(result, blocks)
}

function transformVue(content) {
  let output = content.replace(/(<template\b[^>]*>)([\s\S]*?)(<\/template>)/i, (full, open, template, close) => {
    return `${open}${transformTemplate(template)}${close}`
  })
  output = output.replace(/(<script\b[^>]*>)([\s\S]*?)(<\/script>)/i, (full, open, script, close) => {
    return `${open}${transformJavascript(script)}${close}`
  })
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

export { isLikelyHumanLiteral, replaceHumanText, transformJavascript, transformVue }

function run() {
  let changedFiles = 0
  for (const filePath of walk(SOURCE_ROOT)) {
    const before = fs.readFileSync(filePath, 'utf8')
    const after = path.extname(filePath).toLowerCase() === '.vue'
      ? transformVue(before)
      : transformJavascript(before)
    if (after === before) continue
    fs.writeFileSync(filePath, after, 'utf8')
    changedFiles += 1
    console.log(`corrigido: ${path.relative(path.resolve(SOURCE_ROOT, '..'), filePath)}`)
  }
  console.log(`Arquivos corrigidos: ${changedFiles}`)
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  run()
}
