/**
 * Garante que `font-size`, `padding` e `margin` (incluindo variantes lógicas
 * `-inline`/`-block`/`-top`/`-right`/`-bottom`/`-left`) em `.vue` usem os
 * tokens de design (`var(--font-size-*)`/`var(--space-*)`) em vez de valores
 * `px` soltos.
 *
 * Por que isso é necessário: o levantamento de 2026-09-03 encontrou 172
 * `font-size` e 246 `padding`/`margin` hardcoded espalhados pelo app —
 * exatamente a causa raiz do "tamanho de fonte errado"/"tabela com tamanho
 * errado" relatados. Os PRs #1473/#1477 migraram todo o `.vue` existente
 * para os tokens; este validador impede que a dívida volte a crescer
 * conforme novas telas/componentes forem criados.
 *
 * Verifica tanto `<style scoped>` quanto `style="..."` inline no `<template>`
 * — o regex opera no texto bruto do arquivo, então cobre os dois contextos
 * igual ao padrão já usado em `validate-tooltip-accessible-name.mjs`.
 *
 * Exceções conhecidas e documentadas (valores estruturais/decorativos, não
 * espaçamento de densidade de UI — ver PR #1480 para o raciocínio de cada
 * uma): alinhamento de seta de diagrama em ArquiteturaView.vue e padding
 * vertical de empty-state em SpecsView.vue. Novas exceções legítimas devem
 * ser adicionadas aqui explicitamente, nunca silenciadas com um valor
 * qualquer — a allowlist documenta a decisão, não apenas a suprime.
 */
import { readdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const sourceDirUrl = new URL('../src/', import.meta.url)
const sourceDir = fileURLToPath(sourceDirUrl)

// Termina em `;`/`}` (regra normal de CSS) OU em aspas (`style="font-size:11px"`
// inline no template, sem `;` final antes de fechar o atributo).
const DECLARATION = /\b(font-size|padding|margin)(-top|-right|-bottom|-left|-inline|-block|-inline-start|-inline-end)?\s*:\s*([^;{}"']+)[;}"']/gi

const EXCECOES_CONHECIDAS = new Set([
  'views/ArquiteturaView.vue|padding: var(--space-xs) 0 var(--space-xs) 106px',
  'views/SpecsView.vue|padding: 80px var(--space-xl)',
  // margin:-1px é a técnica padrão "visualmente oculto para leitor de tela"
  // (colapsa a caixa via margin negativa + clip): não é espaçamento de
  // densidade de UI, é parte da técnica de acessibilidade — ver PR #1480.
  'components/UserExperienceGuardrails.vue|margin: -1px',
])

/** Remove o conteúdo de var()/calc()/clamp()/min()/max() para não acusar um
 * `px` que só existe DENTRO da função (ex.: no fallback de um var()). */
export function stripFunctionArgs(value) {
  let result = value
  let previous
  do {
    previous = result
    result = result.replace(/\b(?:var|calc|clamp|min|max)\([^()]*\)/gi, '0')
  } while (result !== previous)
  return result
}

function hasHardcodedPx(value) {
  return /\d+(?:\.\d+)?px/.test(stripFunctionArgs(value))
}

export function findViolationsInFile(filePath, source, relativePath) {
  const violations = []
  for (const match of source.matchAll(DECLARATION)) {
    const [, property, suffix, rawValue] = match
    const value = rawValue.trim()
    if (!hasHardcodedPx(value)) continue

    const declaracao = `${property}${suffix || ''}: ${value}`
    const chave = `${relativePath}|${declaracao}`
    if (EXCECOES_CONHECIDAS.has(chave)) continue

    violations.push({
      file: filePath,
      line: source.slice(0, match.index).split('\n').length,
      declaracao,
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
    const relative = path.relative(sourceDir, file).replace(/\\/g, '/')
    violations.push(...findViolationsInFile(file, await readFile(file, 'utf8'), relative))
  }

  if (violations.length > 0) {
    for (const item of violations) {
      const relative = path.relative(sourceDir, item.file).replace(/\\/g, '/')
      console.error(`  src/${relative}:${item.line} → ${item.declaracao}`)
    }
    throw new Error(
      `${violations.length} declaração(ões) de font-size/padding/margin com px hardcoded. ` +
        'Use os tokens (var(--font-size-*) / var(--space-*), ver src/styles.css) em vez de px solto. ' +
        'Se for um valor genuinamente estrutural/decorativo (não densidade de UI), documente a exceção ' +
        'explicitamente em EXCECOES_CONHECIDAS neste script.',
    )
  }

  console.log(`[design-token-usage] ${files.length} arquivos verificados: nenhum font-size/padding/margin hardcoded fora dos tokens`)
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(`[design-token-usage] validação falhou: ${error.message}`)
    process.exitCode = 1
  })
}
