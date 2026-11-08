// Fontes públicas fixas. Este módulo não recebe token, host ou URL externa.
export const APPROVED_SOURCES = Object.freeze([
  { repository: 'e2e-platform', issue: 10, label: 'E2E físico entre hosts' },
  { repository: 'desktop-pc24x7-runtime', issue: 31, label: 'Readiness do Desktop' },
  { repository: 'noteri-runtime', issue: 42, label: 'Worker Pool Noteri' },
  { repository: 'reqsys-v2-enterprise-real', issue: 3096, label: 'Desktop Admin Broker' },
  { repository: 'engineering-worker-pool', issue: 61, label: 'CAS e Validator pré-PR' },
].map(source => Object.freeze(source)));

const ORIGIN = 'https://api.github.com/repos/ericson-j-santos';
const HTML_ORIGIN = 'https://github.com/ericson-j-santos';

function approvedTarget(target) {
  const match = APPROVED_SOURCES.find(source =>
    source.repository === target?.repository && source.issue === target?.issue);
  if (!match) throw new Error('Fonte não autorizada');
  return match;
}

export function sourceLink(target) {
  const source = approvedTarget(target);
  return HTML_ORIGIN + '/' + source.repository + '/issues/' + source.issue;
}

export async function readPublicIssue(target, fetcher, signal, clock = () => new Date().toISOString()) {
  const source = approvedTarget(target);
  if (typeof fetcher !== 'function') throw new Error('Cliente de leitura ausente');
  const response = await fetcher(ORIGIN + '/' + source.repository + '/issues/' + source.issue, {
    method: 'GET',
    redirect: 'error',
    cache: 'no-store',
    signal,
    headers: { Accept: 'application/vnd.github+json' },
  });
  if (!response?.ok) {
    const status = Number(response?.status);
    if (status === 403 || status === 429) throw new Error('API limitada ou acesso negado');
    throw new Error('Fonte indisponível (HTTP ' + (Number.isFinite(status) ? status : '?') + ')');
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error('Resposta JSON inválida');
  }
  const expectedUrl = sourceLink(source);
  if (!data || typeof data !== 'object' ||
      data.number !== source.issue ||
      (data.state !== 'open' && data.state !== 'closed') ||
      typeof data.title !== 'string' || data.title.trim().length === 0 ||
      typeof data.updated_at !== 'string' ||
      !Number.isFinite(Date.parse(data.updated_at)) ||
      data.html_url !== expectedUrl ||
      data.pull_request !== undefined) {
    throw new Error('Identidade ou contrato da issue inválido');
  }
  return Object.freeze({
    state: data.state,
    title: data.title.slice(0, 170),
    updated: data.updated_at,
    checked: clock(),
  });
}
