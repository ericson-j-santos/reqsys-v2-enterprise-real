import fs from 'node:fs'
import path from 'node:path'

const raiz = process.cwd()
const diretorio = path.join(raiz, 'test-results', 'accessibility')

function lerJson(nome) {
  const arquivo = path.join(diretorio, nome)
  if (!fs.existsSync(arquivo)) {
    throw new Error(`Evidência ausente: ${arquivo}`)
  }
  return JSON.parse(fs.readFileSync(arquivo, 'utf8'))
}

function exigir(condicao, mensagem) {
  if (!condicao) throw new Error(mensagem)
}

const resumo = lerJson('wcag22-resumo.json')
const violacoes = lerJson('wcag22-violacoes.json')
const revisaoManual = lerJson('wcag22-revisao-manual.json')

exigir(resumo.schema_version === 1, 'Versão de esquema WCAG inesperada')
exigir(resumo.rotas_autenticadas === 37, `Esperadas 37 rotas autenticadas; recebido ${resumo.rotas_autenticadas}`)
exigir(resumo.resultado_automatizado === 'approved', `Resultado automatizado não aprovado: ${resumo.resultado_automatizado}`)
exigir(resumo.conformidade_formal === 'pending_manual_audit', 'O teste automatizado não pode declarar conformidade formal sozinho')
exigir(Object.keys(violacoes).length === 0, `Há violações automatizáveis: ${JSON.stringify(violacoes)}`)

const tagsObrigatorias = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']
for (const tag of tagsObrigatorias) {
  exigir(resumo.tags_wcag.includes(tag), `Tag WCAG obrigatória ausente: ${tag}`)
}

const teste = fs.readFileSync(path.join(raiz, 'tests', 'e2e', 'acessibilidade-rotas.spec.js'), 'utf8')
const construcoesProibidas = [
  ['.exclude(', 'exclusão de seletor Axe'],
  ['.disableRules(', 'desativação de regra Axe'],
  ['ALLOWLIST_', 'allowlist técnica'],
  ['EXCECOES_ACEITAS', 'lista de exceções aceitas'],
]

for (const [trecho, descricao] of construcoesProibidas) {
  exigir(!teste.includes(trecho), `Gate inválido: detectada ${descricao} (${trecho})`)
}

const saida = {
  status: 'approved',
  rotas_autenticadas: resumo.rotas_autenticadas,
  violacoes_automatizaveis: 0,
  rotas_com_revisao_manual_axe: Object.keys(revisaoManual).length,
  conformidade_formal: 'pending_manual_audit',
}

fs.writeFileSync(
  path.join(diretorio, 'wcag22-validacao-evidencia.json'),
  `${JSON.stringify(saida, null, 2)}\n`,
  'utf8',
)

console.log(JSON.stringify(saida, null, 2))

if (process.env.GITHUB_STEP_SUMMARY) {
  fs.appendFileSync(
    process.env.GITHUB_STEP_SUMMARY,
    `\n## WCAG 2.2 — evidência automatizada\n\n- Rotas autenticadas: **${saida.rotas_autenticadas}/37**\n- Violações automatizáveis A/AA: **0**\n- Exceções Axe: **0**\n- Rotas com itens Axe para revisão manual: **${saida.rotas_com_revisao_manual_axe}**\n- Conformidade formal: **pendente de auditoria manual**\n`,
  )
}
