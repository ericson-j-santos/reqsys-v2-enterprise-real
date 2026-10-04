/**
 * Garante que todo `<v-tooltip>` com texto também exponha um nome acessível
 * estático.
 *
 * Por que isso é necessário: a Vuetify só renderiza o conteúdo do tooltip
 * enquanto ele está aberto. Com o tooltip fechado — estado padrão quando o
 * axe-core varre a página — o elemento com `role="tooltip"` fica sem nome
 * acessível e a regra `aria-tooltip-name` (WCAG 2.1 AA) acusa violação.
 *
 * O atributo precisa cair no próprio `<v-tooltip>`. `:content-props="{
 * 'aria-label': ... }"` NÃO resolve: aquele prop só alcança o
 * `.v-overlay__content` (filho), enquanto quem carrega `role="tooltip"` é o
 * `.v-overlay` pai. Como VOverlay declara `inheritAttrs: false` e mescla
 * `attrs` explicitamente na raiz, `aria-label` direto no `<v-tooltip>` chega
 * ao elemento certo.
 *
 * Histórico: PR #1484 e #1486 fecharam o shell compartilhado (AppLayout +
 * AmbienteNavigator); este validador impede que a dívida volte a crescer nas
 * telas conforme novos tooltips forem adicionados.
 */
import { readdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const sourceDirUrl = new URL('../src/', import.meta.url)
const sourceDir = fileURLToPath(sourceDirUrl)

const TOOLTIP_TAG = /<v-tooltip\b/gi

/** Localiza o `>` que fecha a tag aberta em `start`, ignorando aspas. */
export function findTagEnd(source, start) {
  let quote = null
  for (let index = start; index < source.length; index += 1) {
    const char = source[index]
    if (quote) {
      if (char === quote) quote = null
    } else if (char === '"' || char === "'") {
      quote = char
    } else if (char === '>') {
      return index
    }
  }
  return -1
}

function hasAttribute(tag, name) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`(?<![\\w:.-])${escaped}(\\s*=|\\s|/|>)`).test(tag)
}

/** Tooltips sem texto (ex.: só com slot default) não têm o que espelhar. */
function hasText(tag) {
  return hasAttribute(tag, 'text') || hasAttribute(tag, ':text')
}

function hasAccessibleName(tag) {
  return hasAttribute(tag, 'aria-label') || hasAttribute(tag, ':aria-label')
}

export function findViolationsInFile(filePath, source) {
  const violations = []
  for (const match of source.matchAll(TOOLTIP_TAG)) {
    const end = findTagEnd(source, match.index)
    if (end === -1) continue
    const tag = source.slice(match.index, end)
    if (!hasText(tag) || hasAccessibleName(tag)) continue
    violations.push({
      file: filePath,
      line: source.slice(0, match.index).split('\n').length,
      tag: tag.replace(/\s+/g, ' ').slice(0, 120),
    })
  }
  return violations
}

async function collectVueFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...(await collectVueFiles(full)))
    } else if (entry.name.endsWith('.vue')) {
      files.push(full)
    }
  }
  return files
}

async function main() {
  const files = await collectVueFiles(sourceDir)
  const violations = []
  for (const file of files) {
    violations.push(...findViolationsInFile(file, await readFile(file, 'utf8')))
  }

  if (violations.length > 0) {
    for (const item of violations) {
      const relative = path.relative(sourceDir, item.file)
      console.error(`  src/${relative}:${item.line} → ${item.tag}`)
    }
    throw new Error(
      `${violations.length} tooltip(s) com texto e sem nome acessível. ` +
        'Acrescente `aria-label` (estático) ou `:aria-label` (dinâmico) espelhando o `text` ' +
        'no próprio <v-tooltip> — não use :content-props, que aplica no elemento errado.',
    )
  }

  console.log(`[tooltip-a11y] ${files.length} arquivos verificados: todo tooltip com texto tem nome acessível`)
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(`[tooltip-a11y] validação falhou: ${error.message}`)
    process.exitCode = 1
  })
}
