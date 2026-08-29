import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url))
const SOURCE_ROOT = path.resolve(SCRIPT_DIR, '..', 'src')

const REPLACEMENTS = [
  [/\bReqSys Teams policy readiness\b/giu, 'Prontidão das políticas do Teams no ReqSys'],
  [/\bMerge readiness\b/giu, 'Prontidão para integração'],
  [/\bCorrelation analytics\b/giu, 'Indicadores de correlação'],
  [/\bGitHub ALM\b/giu, 'ciclo de entrega no GitHub'],
  [/\bPipeline ALM\b/giu, 'Fluxo do ciclo de entrega'],
  [/\bHub Low-Code API\b/giu, 'Central de automações'],
  [/\bHub Low-Code\b/giu, 'Central de automações'],
  [/\bGraph API\b/giu, 'Microsoft Graph'],
  [/\bScore pós-correção\b/giu, 'Nota após correção'],
  [/\bScore de governança\b/giu, 'Nota de governança'],
  [/\bScore atual\b/giu, 'Nota atual'],
  [/\bStatus geral\b/giu, 'Situação geral'],
  [/\bHistórico merge readiness\b/giu, 'Histórico de prontidão para integração'],
  [/\bMerge estabilizado\b/giu, 'Integração estabilizada'],
  [/\bExecutor ALM\b/giu, 'Executor do ciclo de entrega'],
  [/\bCoordenação Geral de ADRs\b/giu, 'Coordenação geral de decisões de arquitetura'],
  [/\bHTTP POST URL do trigger\b/giu, 'Endereço de chamada HTTP POST'],
  [/\bCI\/CD\b/gu, 'integração e publicação automáticas'],
  [/\bWork items?\b/giu, 'Itens de trabalho'],
  [/\bDry[- ]run\b/giu, 'Simulação'],
  [/\bReadiness\b/giu, 'Prontidão'],
  [/\bLaunchpad\b/giu, 'Central de ações'],
  [/\bDashboard\b/giu, 'Painel'],
  [/\bAnalytics\b/giu, 'Indicadores'],
  [/\bRuntime\b/giu, 'Execução'],
  [/\bPipeline\b/giu, 'Fluxo'],
  [/\bWorkspace\b/giu, 'Área de trabalho'],
  [/\bShowcase\b/giu, 'Demonstração'],
  [/\bLogin\b/giu, 'Acesso'],
  [/\bDeployments?\b/giu, 'Implantações'],
  [/\bDeploy\b/giu, 'Implantação'],
  [/\bWorkflows?\b/giu, 'Fluxos de trabalho'],
  [/\bStakeholders?\b/giu, 'Partes interessadas'],
  [/\bFeedback\b/giu, 'Retorno'],
  [/\bRoadmaps?\b/giu, 'Planos de evolução'],
  [/\bCompliance\b/giu, 'Conformidade'],
  [/\bOnboarding\b/giu, 'Integração inicial'],
  [/\bArtifacts?\b/giu, 'Artefatos'],
  [/\bFallback\b/giu, 'Contingência'],
  [/\bTriggers?\b/giu, 'Disparos'],
  [/\bHealth\b/giu, 'Estado operacional'],
  [/\bCards?\b/giu, 'Cartões'],
  [/\bReleases?\b/giu, 'Publicações'],
  [/\bLogs?\b/giu, 'Registros'],
  [/\bEndpoints?\b/giu, 'Pontos de integração'],
  [/\bPayloads?\b/giu, 'Conteúdos das requisições'],
  [/\bRetries\b/giu, 'Novas tentativas'],
  [/\bRetry\b/giu, 'Nova tentativa'],
  [/\bBatches?\b/giu, 'Lotes'],
  [/\bJobs?\b/giu, 'Tarefas'],
  [/\bTimeouts?\b/giu, 'Tempos limite'],
  [/\bRollbacks?\b/giu, 'Reversões'],
  [/\bSmoke\b/giu, 'Verificação rápida'],
  [/\bWebhooks?\b/giu, 'Chamadas automáticas'],
  [/\bPreview\b/giu, 'Prévia'],
  [/\bQueues?\b/giu, 'Filas'],
  [/\bWorkers?\b/giu, 'Processadores'],
  [/\bLow[- ]Code\b/giu, 'Automações'],
  [/\bBackend\b/giu, 'Serviço'],
  [/\bFrontend\b/giu, 'Aplicação'],
  [/\bCache\b/giu, 'Armazenamento temporário'],
  [/\bMock\b/giu, 'Simulação'],
  [/\bFeatures?\b/giu, 'Funcionalidades'],
  [/\bSpecs?\b/giu, 'Especificações'],
  [/\bGates?\b/giu, 'Verificações obrigatórias'],
  [/\bBranches?\b/giu, 'Versões de código'],
  [/\bMerge\b/giu, 'Integração de alterações'],
  [/\bStatus\b/giu, 'Situação'],
  [/\bScore\b/giu, 'Nota'],
  [/\bPRs?\b/gu, 'Solicitações de integração'],
  [/\bCI\b/gu, 'verificações automáticas'],
  [/\bAPI\b/gu, 'serviço'],
  [/\bURL\b/gu, 'endereço'],
  [/\bLLM\b/gu, 'modelo de IA'],
  [/\bPII\b/gu, 'dados pessoais'],
  [/\bSDD\b/gu, 'especificação da solução'],
  [/\bALM\b/gu, 'administração do ciclo de entrega'],
  [/\bADRs?\b/gu, 'decisões de arquitetura'],
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

function transformJavascript(content) {
  let result = content.replace(JS_PROPERTY, (full, name, separator, quote, value) => `${name}${separator}${quote}${replaceHumanText(value)}${quote}`)
  result = result.replace(JS_ASSIGNMENT, (full, name, valueSuffix = '', separator, quote, value) => `${name}${valueSuffix || ''}${separator}${quote}${replaceHumanText(value)}${quote}`)
  return result.replace(JS_FALLBACK, (full, prefix, quote, value) => `${prefix}${quote}${replaceHumanText(value)}${quote}`)
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

function transformTemplate(template) {
  const { protectedTemplate, blocks } = protectBlocks(template)
  let result = protectedTemplate.replace(/>([^<]+)</g, (full, value) => `>${transformTextNode(value)}<`)
  result = result.replace(/\b(aria-label|title|placeholder|label)=(['"])(.*?)\2/giu, (full, name, quote, value) => `${name}=${quote}${replaceHumanText(value)}${quote}`)
  return result.replace(/__REQSYS_LANG_BLOCK_(\d+)__/g, (_, index) => blocks[Number(index)])
}

function transformVue(content) {
  let output = content.replace(/(<template\b[^>]*>)([\s\S]*?)(<\/template>)/i, (full, open, template, close) => `${open}${transformTemplate(template)}${close}`)
  return output.replace(/(<script\b[^>]*>)([\s\S]*?)(<\/script>)/i, (full, open, script, close) => `${open}${transformJavascript(script)}${close}`)
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
