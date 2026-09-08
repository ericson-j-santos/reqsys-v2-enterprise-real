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

const automatizado = lerJson(path.join(diretorioEvidencia, 'wcag22-validacao-evidencia.json'))
const auditoria = lerJson(arquivoAuditoria)

const pendentes = auditoria.manual_criteria.filter((item) => item.status !== 'approved' || !Array.isArray(item.evidence) || item.evidence.length === 0)
const formalAprovado = automatizado.status === 'approved' && pendentes.length === 0 && auditoria.formal_status === 'approved'

const resultado = {
  status: formalAprovado ? 'approved' : 'pending_manual_audit',
  automated_status: automatizado.status,
  pending_manual_criteria: pendentes.map((item) => ({ id: item.id, description: item.description })),
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
    `\n## WCAG 2.2 AA — prontidão formal\n\n- Evidência automatizada: **${automatizado.status}**\n- Critérios manuais pendentes: **${pendentes.length}**\n- Estado formal: **${resultado.status}**\n`,
  )
}

if (!formalAprovado) process.exitCode = 2
