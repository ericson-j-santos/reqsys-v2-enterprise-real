import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  GitBranch,
  GitPullRequest,
  Info,
  LockKeyhole,
  RefreshCcw,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import './GitHubReadOnly.css';

type DemandSource = {
  id: string;
  title: string;
  repo: string;
  url: string;
  reference: string;
  sha: string;
  priority: string;
};

type PublicReference = {
  kind: 'Issue' | 'PR';
  number: number;
  title: string;
  state: string;
  updatedAt: string;
  url: string;
  mergedAt: string | null;
};

type SourceResult = {
  demandId: string;
  repository: string;
  branch: string;
  headSha: string;
  checkedAt: string;
  rateRemaining: number | null;
  reference: PublicReference | null;
};

const PUBLIC_REPOSITORIES = new Set([
  'ericson-j-santos/e2e-platform',
  'ericson-j-santos/reqsys-v2-enterprise-real',
  'ericson-j-santos/engineering-orchestrator',
  'ericson-j-santos/engineering-worker-pool',
  'ericson-j-santos/transferidor-documental',
  'ericson-j-santos/noteri-runtime',
  'ericson-j-santos/desktop-pc24x7-runtime',
]);

function resolvePublicTarget(demand: DemandSource):
  | { repo: string; reference: { kind: 'issues' | 'pulls'; number: number } | null }
  | { reason: string } {
  const repo = demand.repo.trim().toLowerCase();
  if (!PUBLIC_REPOSITORIES.has(repo)) {
    return { reason: 'Repositório fora da lista pública permitida. Nenhuma consulta será realizada.' };
  }

  const url = demand.url.trim();
  if (!url || url === 'https://github.com/' + repo || url === 'https://github.com/' + repo + '/') {
    return { repo, reference: null };
  }

  const match = /^https:\/\/github\.com\/([a-z0-9._-]+\/[a-z0-9._-]+)\/(issues|pull)\/([1-9]\d{0,7})\/?$/i.exec(url);
  if (!match || match[1].toLowerCase() !== repo) {
    return { reason: 'Referência não corresponde à URL canônica de issue/PR deste repositório.' };
  }
  return {
    repo,
    reference: {
      kind: match[2] === 'pull' ? 'pulls' : 'issues',
      number: Number(match[3]),
    },
  };
}

function asObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('A API retornou conteúdo incompatível com o contrato.');
  }
  return value as Record<string, unknown>;
}

async function getPublicJson(
  path: string,
  signal: AbortSignal,
): Promise<{ data: Record<string, unknown>; remaining: number | null }> {
  const response = await fetch('https://api.github.com' + path, {
    method: 'GET',
    mode: 'cors',
    credentials: 'omit',
    redirect: 'error',
    cache: 'no-store',
    signal,
    headers: {
      Accept: 'application/vnd.github+json',
    },
  });

  const remainingHeader = response.headers.get('x-ratelimit-remaining');
  const remaining = remainingHeader !== null && /^\d+$/.test(remainingHeader)
    ? Number(remainingHeader)
    : null;

  if (response.status === 403 || response.status === 429) {
    throw new Error('Acesso limitado pelo GitHub (HTTP ' + response.status +
      '). Não repetir até a janela oficial de cota ser restaurada.');
  }
  if (response.status === 404) {
    throw new Error('Repositório ou referência não acessível publicamente (HTTP 404).');
  }
  if (!response.ok) {
    throw new Error('Consulta pública não concluída: HTTP ' + response.status + '.');
  }

  const payload: unknown = await response.json();
  return { data: asObject(payload), remaining };
}

function formatDate(value: string) {
  if (!value) return 'Não informado';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? 'Data inválida'
    : date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

export default function GitHubReadOnly({
  demands,
  initialDemandId,
}: {
  demands: DemandSource[];
  initialDemandId: string;
}) {
  const [demandId, setDemandId] = useState(initialDemandId);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SourceResult | null>(null);
  const [error, setError] = useState('');
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const demand = demands.find(item => item.id === demandId) || demands[0];
  const target = useMemo(
    () => demand ? resolvePublicTarget(demand) : { reason: 'Nenhuma demanda cadastrada.' },
    [demand],
  );
  const limitation = 'reason' in target ? target.reason : '';
  const insufficientQuota = result?.rateRemaining !== null &&
    result?.rateRemaining !== undefined && result.rateRemaining < 3;

  function chooseDemand(nextId: string) {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setLoading(false);
    setError('');
    setResult(null);
    setDemandId(nextId);
  }

  async function consult() {
    if (!demand || 'reason' in target || loading || insufficientQuota) return;

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setResult(null);
    setError('');
    const timeoutId = window.setTimeout(() => controller.abort(), 9000);

    try {
      const repoPath = '/repos/' + target.repo;
      const repoResponse = await getPublicJson(repoPath, controller.signal);
      const repository = repoResponse.data;
      if (
        repository.private !== false ||
        repository.full_name !== target.repo ||
        typeof repository.default_branch !== 'string' ||
        !/^[a-z0-9._/-]{1,100}$/i.test(repository.default_branch)
      ) {
        throw new Error('Identidade pública do repositório não validada.');
      }

      const head = await getPublicJson(
        repoPath + '/commits/' + encodeURIComponent(repository.default_branch),
        controller.signal,
      );
      if (typeof head.data.sha !== 'string' || !/^[a-f0-9]{40}$/i.test(head.data.sha)) {
        throw new Error('HEAD público não pôde ser confirmado.');
      }

      let reference: PublicReference | null = null;
      let remaining = head.remaining ?? repoResponse.remaining;
      if (target.reference) {
        const ref = target.reference;
        const source = await getPublicJson(
          repoPath + '/' + ref.kind + '/' + ref.number,
          controller.signal,
        );
        const item = source.data;
        remaining = source.remaining ?? remaining;
        if (
          item.number !== ref.number ||
          typeof item.title !== 'string' ||
          (item.state !== 'open' && item.state !== 'closed') ||
          typeof item.html_url !== 'string'
        ) {
          throw new Error('Número ou estado da referência inconsistente com a origem.');
        }

        const expectedUrl = 'https://github.com/' + target.repo + '/' +
          (ref.kind === 'pulls' ? 'pull' : 'issues') + '/' + ref.number;
        if (item.html_url !== expectedUrl) {
          throw new Error('URL de referência divergente da origem admitida.');
        }

        reference = {
          kind: ref.kind === 'pulls' ? 'PR' : 'Issue',
          number: ref.number,
          title: item.title.slice(0, 240),
          state: String(item.state),
          updatedAt: typeof item.updated_at === 'string' ? item.updated_at : '',
          url: expectedUrl,
          mergedAt: ref.kind === 'pulls' && typeof item.merged_at === 'string'
            ? item.merged_at
            : null,
        };
      }

      if (controller.signal.aborted || controllerRef.current !== controller) return;
      setResult({
        demandId: demand.id,
        repository: target.repo,
        branch: repository.default_branch,
        headSha: head.data.sha,
        checkedAt: new Date().toISOString(),
        rateRemaining: remaining,
        reference,
      });
    } catch (reason) {
      // A consulta cancelada não pode modificar o resultado da demanda seguinte.
      if (controllerRef.current !== controller) return;
      if (controller.signal.aborted) {
        setError('Tempo de consulta excedido ou leitura interrompida. Nenhuma evidência foi homologada.');
      } else if (reason instanceof Error) {
        setError(reason.message.startsWith('Failed to fetch')
          ? 'A consulta pública falhou por conexão, CORS ou indisponibilidade. Estado não verificado.'
          : reason.message);
      } else {
        setError('Não foi possível validar a fonte pública.');
      }
    } finally {
      window.clearTimeout(timeoutId);
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setLoading(false);
      }
    }
  }

  return (
    <section className="public-sources">
      <div className="public-sources-heading">
        <div>
          <span className="public-eyebrow">FONTE PÚBLICA · CONSULTA DIRETA</span>
          <h1>Fontes GitHub</h1>
          <p>
            Inspecione a referência pública e o HEAD da branch padrão.
            Esta leitura não altera o estado da demanda, do TODO Global ou do host.
          </p>
        </div>
        <span className="public-readonly-tag"><LockKeyhole size={15} /> Somente GET</span>
      </div>

      <div className="public-info-banner">
        <ShieldCheck size={19} />
        <div>
          <strong>Consulta sem token, sem comandos e sem sincronização automática.</strong>
          <span>
            As informações obtidas são temporárias e dependem da disponibilidade pública do GitHub.
            Sem resposta, nenhuma decisão operacional é promovida.
          </span>
        </div>
      </div>

      <div className="public-layout">
        <div className="public-panel">
          <h2>Selecionar demanda</h2>
          <label className="public-input-label" htmlFor="github-demand">Demandas em escopo</label>
          <select
            id="github-demand"
            value={demand?.id || ''}
            onChange={event => chooseDemand(event.target.value)}
          >
            {demands.map(item => (
              <option key={item.id} value={item.id}>
                {item.priority + ' · ' + item.title}
              </option>
            ))}
          </select>

          <div className="public-mini-grid">
            <div><span>Repositório registrado</span><strong>{demand?.repo || '—'}</strong></div>
            <div><span>Referência registrada</span><strong>{demand?.reference || 'Sem issue/PR'}</strong></div>
            <div><span>SHA admitido localmente</span><strong className="public-mono">{demand?.sha || 'Não informado'}</strong></div>
          </div>

          {limitation && (
            <div className="public-alert public-alert-danger" role="alert">
              <ShieldAlert size={17} /><span>{limitation}</span>
            </div>
          )}
          {insufficientQuota && (
            <div className="public-alert public-alert-warning" role="alert">
              <AlertTriangle size={17} />
              <span>Cota pública insuficiente para outra consulta completa. Aguarde a renovação oficial.</span>
            </div>
          )}
          <button
            className="public-primary-btn"
            onClick={consult}
            disabled={Boolean(limitation) || loading || insufficientQuota}
            type="button"
          >
            <RefreshCcw size={16} />
            {loading ? 'Consultando fonte pública...' : 'Consultar GitHub (somente leitura)'}
          </button>
          <p className="public-caption">
            Até 3 solicitações GET por consulta. Sem polling, credenciais ou escrita.
            O GitHub limita consultas públicas não autenticadas por IP.
          </p>
        </div>

        <div className="public-panel public-result">
          <div className="public-result-title">
            <h2>Readback da fonte</h2>
            <span className="public-unverified">Não é certificação operacional</span>
          </div>

          {error ? (
            <div className="public-alert public-alert-danger" role="alert">
              <ShieldAlert size={18} /><span>{error}</span>
            </div>
          ) : result && result.demandId === demand?.id ? (
            <div className="public-record">
              <div className="public-record-success">
                <CheckCircle2 size={19} />
                <div>
                  <strong>Leitura pública concluída</strong>
                  <small>Origem consultada: api.github.com · {formatDate(result.checkedAt)}</small>
                </div>
              </div>
              <div className="public-mini-grid">
                <div>
                  <span>Branch padrão pública</span>
                  <strong>{result.branch}</strong>
                </div>
                <div>
                  <span>HEAD público — não é SHA admitido</span>
                  <strong className="public-mono">{result.headSha}</strong>
                </div>
              </div>
              <a
                className="public-link"
                href={'https://github.com/' + result.repository}
                rel="noopener noreferrer"
                target="_blank"
              >
                <GitBranch size={15} /> Abrir repositório público <ArrowUpRight size={14} />
              </a>
              {result.reference ? (
                <div className="public-reference">
                  <div className="public-reference-head">
                    <GitPullRequest size={18} />
                    <strong>{result.reference.kind} #{result.reference.number}</strong>
                    <span>{result.reference.state === 'open' ? 'Aberta' : 'Fechada'}</span>
                  </div>
                  <p>{result.reference.title}</p>
                  <small>
                    Atualizada em {formatDate(result.reference.updatedAt)}
                    {result.reference.mergedAt ? ' · Integração registrada na origem' : ''}
                  </small>
                  <a className="public-link" href={result.reference.url} target="_blank" rel="noopener noreferrer">
                    Abrir referência no GitHub <ArrowUpRight size={14} />
                  </a>
                </div>
              ) : (
                <div className="public-alert public-alert-warning">
                  <Info size={16} /> Não há issue ou PR canônica informada para esta demanda.
                </div>
              )}
              <div className="public-caption">
                {result.rateRemaining === null
                  ? 'Cota restante não informada pelo GitHub.'
                  : 'Cota pública informada após a consulta: ' + result.rateRemaining + ' requisições.'}
              </div>
            </div>
          ) : (
            <div className="public-empty">
              <Clock3 size={31} />
              <strong>Aguardando consulta explícita</strong>
              <span>
                Selecione uma demanda e consulte a fonte pública.
                Nenhuma evidência é recuperada automaticamente.
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="public-limits">
        <h2>Limites de confiança</h2>
        <div className="public-limits-grid">
          <div><strong>Observação</strong><span>Issue/PR e HEAD público vindos da API oficial.</span></div>
          <div><strong>Não comprovado</strong><span>SHA de execução, gates, runner, lease e checkpoint real.</span></div>
          <div><strong>Consequência</strong><span>ready_for_work = false. Dispatch, merge e deploy indisponíveis.</span></div>
        </div>
        <p>
          A leitura é uma fonte primária pública, não um Validator independente nem um
          comprovante de E2E físico. Repositórios privados continuam fora do escopo;
          não adicione dados pessoais, segredos ou detalhes internos.
        </p>
      </div>
    </section>
  );
}
