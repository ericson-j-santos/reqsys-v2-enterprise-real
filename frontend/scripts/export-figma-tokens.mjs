import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDirectory = dirname(fileURLToPath(import.meta.url))
const frontendDirectory = resolve(scriptDirectory, '..')
const sourcePath = resolve(frontendDirectory, 'src/theme/design-tokens.json')
const outputDirectory = resolve(frontendDirectory, 'artifacts/figma-tokens')
const artifactPath = resolve(outputDirectory, 'reqsys.tokens.json')
const manifestPath = resolve(outputDirectory, 'manifest.json')
const checksumPath = resolve(outputDirectory, 'reqsys.tokens.sha256')
const driftReportPath = resolve(outputDirectory, 'drift-report.json')

function sortObjectEntries(object, mapper) {
  return Object.fromEntries(
    Object.entries(object)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, value]) => [key, mapper(value, key)]),
  )
}

function normalize(value) {
  if (Array.isArray(value)) {
    return value.map(normalize)
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, nestedValue]) => [key, normalize(nestedValue)]),
    )
  }

  return value
}

function serialize(value) {
  return `${JSON.stringify(normalize(value), null, 2)}\n`
}

async function main() {
  const source = JSON.parse(await readFile(sourcePath, 'utf8'))
  const version = source.metadata?.version

  if (!version || !/^\d+\.\d+\.\d+$/.test(version)) {
    throw new Error(`metadata.version deve seguir SemVer; recebido: ${version ?? 'ausente'}`)
  }

  const artifact = {
    reqsys: {
      color: sortObjectEntries(source.colors, (value) => ({ $type: 'color', $value: value })),
      radius: sortObjectEntries(source.radius, (value) => ({ $type: 'dimension', $value: value })),
      fontFamily: {
        base: { $type: 'fontFamily', $value: source.typography.fontFamily },
      },
      semantic: sortObjectEntries(source.semantic, (value) => ({
        $type: 'color',
        $value: `{reqsys.color.${value}}`,
      })),
    },
    $themes: [
      {
        id: 'reqsys-default',
        name: 'ReqSys Default',
        selectedTokenSets: { reqsys: 'enabled' },
      },
    ],
    $metadata: {
      tokenSetOrder: ['reqsys'],
      version,
    },
  }

  const artifactContent = serialize(artifact)
  const sha256 = createHash('sha256').update(artifactContent).digest('hex')
  const tokenCounts = {
    colors: Object.keys(source.colors).length,
    radius: Object.keys(source.radius).length,
    fontFamily: 1,
    semantic: Object.keys(source.semantic).length,
  }
  tokenCounts.total = Object.values(tokenCounts).reduce((total, count) => total + count, 0)

  const manifest = {
    artifact: 'reqsys-figma-tokens',
    format: 'figma-tokens-studio',
    schemaVersion: '1',
    sha256,
    source: 'frontend/src/theme/design-tokens.json',
    tokenCounts,
    version,
  }

  const driftReport = {
    artifact: 'frontend/artifacts/figma-tokens/reqsys.tokens.json',
    driftDetected: false,
    policy: 'Generated artifact must match canonical design tokens; CI fails on repository diff.',
    sha256,
    source: 'frontend/src/theme/design-tokens.json',
    status: 'clean',
    version,
  }

  await mkdir(outputDirectory, { recursive: true })
  await Promise.all([
    writeFile(artifactPath, artifactContent),
    writeFile(manifestPath, serialize(manifest)),
    writeFile(checksumPath, `${sha256}  reqsys.tokens.json\n`),
    writeFile(driftReportPath, serialize(driftReport)),
  ])

  console.log(`[figma-tokens] artefato v${version} gerado com ${tokenCounts.total} tokens`)
  console.log(`[figma-tokens] sha256=${sha256}`)
}

main().catch((error) => {
  console.error(`[figma-tokens] exportação falhou: ${error.message}`)
  process.exitCode = 1
})
