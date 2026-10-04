import fs from 'node:fs'
import path from 'node:path'

const raizFrontend = process.cwd()
const raizRepo = path.resolve(raizFrontend, '..')
const diretorioEvidencia = path.join(raizFrontend, 'test-results', 'accessibility')
const arquivoAuditoria = path.join(raizRepo, 'governance', 'accessibility', 'wcag22-aa-manual-audit.json')

function lerJson(arquivo) {
  if (!fs.existsSync(arquivo)) throw new Error(`Arquivo ausente: ${arquivo}`)
  return JSON.parse(fs.readFileSync(arquivo, 'utf8'))
}

function lerJsonOpcional(arquivo) {
  if (!fs.existsSync(arquivo)) return null
  return JSON.parse(fs.readFileSync(arquivo, 'utf8'))
}

const automatizado = lerJson(path.join(diretorioEvidencia, 'wcag22-validacao-evidencia.json'))
const auditoria = lerJson(arquivoAuditoria)

/**
 * Critérios marcados como `automated_gate` só contam como satisfeitos quando a
 * execução vigente publica evidência aprovada para o mesmo id. Arquivo ausente,
 * validação reprovada ou id faltante devolvem o critério à condição de
 * pendência — fail-closed, sem reaproveitar evidência de execução anterior.
 */
const criteriosAutomatizados = lerJsonOpcional(
  path.join(diretorioEvidencia, 'wcag22-criterios-automatizados.json'),
)
const validacaoAutomatizada = lerJsonOpcional(
  path.join(diretorioEvidencia, 'wcag22-criterios-automatizados-validacao.json'),
)

function criterioAutomatizadoAprovado(id) {
  if (validacaoAutomatizada?.status !== 'approved') return false
  return criteriosAutomatizados?.criterios?.[id]?.status === 'approved'
}

function criterioSatisfeito(item) {
  if (item.status === 'automated_gate') return criterioAutomatizadoAprovado(item.id)
  return item.status === 'approved' && Array.isArray(item.evidence) && item.evidence.length > 0
}

const pendentes = auditoria.manual_criteria.filter((item) => !criterioSatisfeito(item))
const pendentesHumanos = pendentes.filter((item) => item.status !== 'automated_gate')
const automatizadosReprovados = pendentes.filter((item) => item.status === 'automated_gate')

const formalAprovado =
  automatizado.status === 'approved' && pendentes.length === 0 && auditoria.formal_status === 'approved'

const resultado = {
  status: formalAprovado ? 'approved' : 'pending_manual_audit',
  automated_status: automatizado.status,
  automated_criteria_status: validacaoAutomatizada?.status ?? 'missing',
  pending_manual_criteria: pendentesHumanos.map((item) => ({ id: item.id, description: item.description })),
  failed_automated_criteria: automatizadosReprovados.map((item) => ({
    id: item.id,
    description: item.description,
  })),
}

fs.mkdirSync(diretorioEvidencia, { recursive: true })
fs.writeFileSync(
  path.join(diretorioEvidencia, 'wcag22-formal-readiness.json'),
  `${JSON.stringify(resultado, null, 2)}\n`,
  'utf8',
)

console.log(JSON.stringify(resultado, null, 2))

if (process.env.GITHUB_STEP_SUMMARY) {
  fs.appendFileSync(
    process.env.GITHUB_STEP_SUMMARY,
    `\n## WCAG 2.2 AA — prontidão formal\n\n` +
      `- Evidência automatizada (axe): **${automatizado.status}**\n` +
      `- Critérios automatizados de teclado/foco: **${resultado.automated_criteria_status}**\n` +
      `- Critérios automatizados reprovados: **${resultado.failed_automated_criteria.length}**\n` +
      `- Critérios manuais pendentes: **${resultado.pending_manual_criteria.length}**\n` +
      `- Estado formal: **${resultado.status}**\n`,
  )
}

if (!formalAprovado) process.exitCode = 2
