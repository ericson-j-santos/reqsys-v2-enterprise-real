import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const dashboardDir = path.join(root, 'docs', 'dashboard');
const reportJson = path.join(dashboardDir, 'dashboard-regression-report.json');
const reportMd = path.join(dashboardDir, 'dashboard-regression-report.md');

const requiredCards = [
  'Success rate', 'P95 lead time', 'Predictive risk score', 'Maturity score',
  'Release readiness', 'Command center', 'Contracts validation', 'Tracked PRs',
  'Merge rate', 'Delivery maturity', 'Delivery readiness', 'Delivery completion',
  'Completion gap', 'Delivery readiness gap', 'Delivery total gap',
  'Largest delivery gap', 'Delivery evidences', 'Evidence coverage',
  'Artifacts catalogados', 'Schema coverage', 'Baseline incidente'
];

const evidenceHubRequiredCards = [
  'Delivery readiness', 'Delivery completion', 'Delivery finalization', 'Maturity snapshot',
  'Observability mapped', 'Contract artifacts', 'Dashboard regression',
  'Traceability domains', 'Risco operacional consolidado'
];

const evidenceHubJsonSources = [
  '../audit/delivery-readiness/delivery-readiness-report.json',
  '../audit/delivery-completion/delivery-completion-snapshot.json',
  '../audit/delivery-finalization/delivery-finalization-report.json',
  '../audit/delivery-maturity/delivery-maturity-snapshot.json',
  '../artifacts/observability-correlation-report/observability-correlation-report.json',
  '../audit/artifact-contract-validation/artifact-contract-validation-report.json',
  'dashboard-regression-report.json',
  '../audit/living-architecture/living-architecture-traceability-report.json',
  '../traceability/living-architecture-map.json'
];

const evidenceHubSections = [
  'delivery-readiness', 'delivery-completion', 'delivery-finalization', 'maturity-snapshot',
  'observability-correlation', 'artifact-contract-validation', 'dashboard-regression',
  'living-architecture-traceability'
];

const expectedJsonSources = [
  '../audit/ci-lead-time-analytics.json',
  '../audit/history/operational-history-snapshot.json',
  '../audit/predictive/runtime-predictive-analytics.json',
  '../audit/maturity/operational-maturity-score.json',
  '../audit/artifact-discovery/operational-artifact-discovery-index.json',
  '../audit/release-readiness/golden-release-readiness.json',
  '../audit/command-center/command-center-readiness.json',
  '../audit/extended-contract-validation/extended-operational-contract-validation.json',
  '../audit/delivery/delivery-status-report.json',
  '../audit/delivery-burndown/delivery-burndown-snapshot.json',
  '../audit/delivery-evidence/delivery-evidence-report.json',
  '../audit/delivery-readiness/delivery-readiness-report.json',
  '../audit/delivery-completion/delivery-completion-snapshot.json'
];

const secretPatterns = [
  { name: 'private_key', regex: /-----BEGIN (?:RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----/i },
  { name: 'github_token', regex: /gh[pousr]_[A-Za-z0-9_]{20,}/ },
  { name: 'jwt', regex: /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/ },
  { name: 'aws_access_key', regex: /AKIA[0-9A-Z]{16}/ },
  { name: 'slack_token', regex: /xox[baprs]-[A-Za-z0-9-]{10,}/ },
  { name: 'assignment_secret', regex: /(?:api[_-]?key|token|secret|password|senha)\s*=\s*['\"][^'\"]{8,}['\"]/i }
];

const externalCallPatterns = [
  /https?:\/\//i,
  /\/\/cdn\./i,
  /fetch\(\s*['\"]https?:\/\//i,
  /import\s*\([^)]*https?:\/\//i,
  /<script[^>]+src=["']https?:\/\//i,
  /<link[^>]+href=["']https?:\/\//i
];

function readText(file) {
  return fs.readFileSync(file, 'utf8');
}

function pass(name, details = {}) { return { name, status: 'passed', severity: 'report-only', ...details }; }
function gap(name, details = {}) { return { name, status: 'gap', severity: 'report-only', ...details }; }

const htmlFiles = fs.readdirSync(dashboardDir)
  .filter((file) => file.endsWith('.html'))
  .sort()
  .map((file) => path.join(dashboardDir, file));

const checks = [];
checks.push(htmlFiles.length > 0
  ? pass('dashboards_html_identificados', { files: htmlFiles.map((file) => path.relative(root, file)) })
  : gap('dashboards_html_identificados', { message: 'Nenhum dashboard HTML encontrado em docs/dashboard/.' }));

const files = Object.fromEntries(htmlFiles.map((file) => [path.relative(root, file), readText(file)]));
const dynamicPath = path.join('docs', 'dashboard', 'live-operational-dashboard.dynamic.html');
const dynamicHtml = files[dynamicPath] ?? '';
const evidenceHubPath = path.join('docs', 'dashboard', 'operational-evidence-hub.html');
const evidenceHubHtml = files[evidenceHubPath] ?? '';

const missingCards = requiredCards.filter((label) => !dynamicHtml.includes(`card('${label}'`) && !dynamicHtml.includes(`card("${label}"`) && !dynamicHtml.includes(label));
checks.push(missingCards.length === 0
  ? pass('cards_obrigatorios_presentes', { expected: requiredCards.length })
  : gap('cards_obrigatorios_presentes', { missing: missingCards }));

const missingSources = expectedJsonSources.filter((href) => !dynamicHtml.includes(href));
checks.push(missingSources.length === 0
  ? pass('fontes_json_esperadas_referenciadas', { expected: expectedJsonSources.length })
  : gap('fontes_json_esperadas_referenciadas', { missing: missingSources }));

const fallbackSignals = ['const fallback', 'async function loadJson', 'try {', 'catch (error)', 'fallback[source.key]', 'response.ok'];
const missingFallbackSignals = fallbackSignals.filter((signal) => !dynamicHtml.includes(signal));
checks.push(missingFallbackSignals.length === 0
  ? pass('fallback_seguro_para_artifact_ausente')
  : gap('fallback_seguro_para_artifact_ausente', { missingSignals: missingFallbackSignals }));

if (evidenceHubHtml) {
  const missingHubCards = evidenceHubRequiredCards.filter((label) => !evidenceHubHtml.includes(label));
  checks.push(missingHubCards.length === 0
    ? pass('evidence_hub_cards_executivos_presentes', { expected: evidenceHubRequiredCards.length })
    : gap('evidence_hub_cards_executivos_presentes', { missing: missingHubCards }));

  const missingHubSources = evidenceHubJsonSources.filter((href) => !evidenceHubHtml.includes(href));
  checks.push(missingHubSources.length === 0
    ? pass('evidence_hub_fontes_json_referenciadas', { expected: evidenceHubJsonSources.length })
    : gap('evidence_hub_fontes_json_referenciadas', { missing: missingHubSources }));

  const missingHubSections = evidenceHubSections.filter((section) => !evidenceHubHtml.includes('id="' + section + '"'));
  checks.push(missingHubSections.length === 0
    ? pass('evidence_hub_drill_down_navegavel', { expected: evidenceHubSections.length })
    : gap('evidence_hub_drill_down_navegavel', { missing: missingHubSections }));

  const hubFallbackSignals = ['const fallback', 'async function loadJson', 'try {', 'catch (error)', 'response.ok', 'fallback[domain.key]'];
  const missingHubFallback = hubFallbackSignals.filter((signal) => !evidenceHubHtml.includes(signal));
  checks.push(missingHubFallback.length === 0
    ? pass('evidence_hub_fallback_seguro')
    : gap('evidence_hub_fallback_seguro', { missingSignals: missingHubFallback }));

  const hubGovernanceSignals = ['confidence_level', 'operational_risk', 'semaforo', 'runbook', 'contract'];
  const missingHubGovernance = hubGovernanceSignals.filter((signal) => !evidenceHubHtml.includes(signal));
  checks.push(missingHubGovernance.length === 0
    ? pass('evidence_hub_indicadores_governanca_presentes')
    : gap('evidence_hub_indicadores_governanca_presentes', { missing: missingHubGovernance }));
} else {
  checks.push(gap('evidence_hub_html_presente', { message: 'operational-evidence-hub.html não encontrado em docs/dashboard/.' }));
}

for (const [file, content] of Object.entries(files)) {
  const secrets = secretPatterns.filter((pattern) => pattern.regex.test(content)).map((pattern) => pattern.name);
  checks.push(secrets.length === 0
    ? pass(`ausencia_de_secrets:${file}`)
    : gap(`ausencia_de_secrets:${file}`, { findings: secrets }));

  const externalFindings = externalCallPatterns.filter((regex) => regex.test(content)).map((regex) => regex.toString());
  checks.push(externalFindings.length === 0
    ? pass(`ausencia_de_chamadas_externas_nao_governadas:${file}`)
    : gap(`ausencia_de_chamadas_externas_nao_governadas:${file}`, { findings: externalFindings }));

  const localSignals = ['<!doctype html>', '<html lang="pt-BR"', '<meta name="viewport"'];
  const missingLocalSignals = localSignals.filter((signal) => !content.includes(signal));
  checks.push(missingLocalSignals.length === 0
    ? pass(`compatibilidade_basica_execucao_local:${file}`)
    : gap(`compatibilidade_basica_execucao_local:${file}`, { missingSignals: missingLocalSignals }));
}

const summary = {
  generated_at: new Date().toISOString(),
  mode: 'report-only',
  dashboard_dir: 'docs/dashboard',
  totals: {
    checks: checks.length,
    passed: checks.filter((check) => check.status === 'passed').length,
    gaps: checks.filter((check) => check.status === 'gap').length
  }
};

const report = {
  summary,
  required_cards: requiredCards,
  expected_json_sources: expectedJsonSources,
  evidence_hub: {
    required_cards: evidenceHubRequiredCards,
    expected_json_sources: evidenceHubJsonSources,
    drill_down_sections: evidenceHubSections
  },
  checks
};
fs.writeFileSync(reportJson, `${JSON.stringify(report, null, 2)}\n`);

const statusIcon = (status) => status === 'passed' ? '✅' : '⚠️';
const rows = checks.map((check) => `| ${statusIcon(check.status)} ${check.name} | ${check.status} | ${check.severity} | ${check.missing ? check.missing.join('<br>') : check.findings ? check.findings.join('<br>') : check.message ?? '-'} |`).join('\n');
const md = `# Dashboard Regression Report\n\n` +
  `Modo: **report-only**. Este relatório não bloqueia CI na primeira versão; gaps devem ser tratados como backlog governado.\n\n` +
  `Gerado em: ${summary.generated_at}\n\n` +
  `## Resumo\n\n` +
  `- Checks: ${summary.totals.checks}\n` +
  `- Passou: ${summary.totals.passed}\n` +
  `- Gaps report-only: ${summary.totals.gaps}\n\n` +
  `## Dashboards HTML identificados\n\n` +
  htmlFiles.map((file) => `- \`${path.relative(root, file)}\``).join('\n') +
  `\n\n## Checks\n\n| Check | Status | Severidade | Detalhe |\n| --- | --- | --- | --- |\n${rows}\n`;
fs.writeFileSync(reportMd, md);

console.log(`Dashboard regression report-only: ${summary.totals.passed}/${summary.totals.checks} checks passed; ${summary.totals.gaps} gaps.`);
console.log(`JSON: ${path.relative(root, reportJson)}`);
console.log(`Markdown: ${path.relative(root, reportMd)}`);
process.exit(0);
