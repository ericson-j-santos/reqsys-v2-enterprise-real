import { useEffect, useState } from 'react';
import { AlertCircle, Clock3, GitBranch, RefreshCcw, ShieldAlert } from 'lucide-react';

type Target = { repository: string; issue: number; label: string };
type Snapshot = {
  target: Target; state: 'open' | 'closed' | 'unknown';
  title: string; updated: string; checked: string; error: string;
};
const TARGETS: Target[] = [
  { repository: 'e2e-platform', issue: 10, label: 'E2E físico entre hosts' },
  { repository: 'desktop-pc24x7-runtime', issue: 31, label: 'Readiness do Desktop' },
  { repository: 'noteri-runtime', issue: 42, label: 'Worker Pool Noteri' },
  { repository: 'reqsys-v2-enterprise-real', issue: 3096, label: 'Desktop Admin Broker' },
  { repository: 'engineering-worker-pool', issue: 61, label: 'CAS e Validator pré-PR' }
];
const unknown = (target: Target, error = 'Não consultado'): Snapshot =>
  ({ target, state: 'unknown', title: '', updated: '', checked: '', error });
let memo: { time: number; items: Snapshot[] } | undefined;
async function inspect(target: Target, signal: AbortSignal): Promise<Snapshot> {
  // Lista de destinos fixa; nunca consumir URL arbitrária nem tokens do navegador.
  const path = 'https://api.github.com/repos/ericson-j-santos/' + target.repository + '/issues/' + target.issue;
  const response = await fetch(path, { signal, cache: 'no-store',
    headers: { Accept: 'application/vnd.github+json' } });
  if (!response.ok) throw Error('HTTP ' + response.status + ' (sem leitura confirmada)');
  const data: unknown = await response.json();
  if (!data || typeof data !== 'object') throw Error('Contrato JSON inválido');
  const value = data as Record<string, unknown>;
  if (value.number !== target.issue || (value.state !== 'open' && value.state !== 'closed')
    || typeof value.updated_at !== 'string' || typeof value.title !== 'string') {
    throw Error('Resposta inconsistente');
  }
  return { target, state: value.state, title: value.title.slice(0, 170),
    updated: value.updated_at, checked: new Date().toISOString(), error: '' };
}
function date(iso: string) {
  if (!iso) return 'Não verificada';
  const value = new Date(iso);
  return Number.isNaN(value.getTime()) ? 'Data inválida' : value.toLocaleString('pt-BR');
}
export default function PublicGithubReadOnly() {
  const [items, setItems] = useState<Snapshot[]>(memo?.items || TARGETS.map(t => unknown(t)));
  const [busy, setBusy] = useState(false);
  const [time, setTime] = useState(memo?.time || 0);
  async function refresh(force = false) {
    if (!force && memo && Date.now() - memo.time < 300000) {
      setItems(memo.items); setTime(memo.time); return;
    }
    setBusy(true);
    const controller = new AbortController();
    const limit = setTimeout(() => controller.abort(), 10000);
    try {
      const result = await Promise.all(TARGETS.map(async target => {
        try { return await inspect(target, controller.signal); }
        catch (error) {
          return unknown(target, error instanceof Error ? error.message : 'Falha inesperada');
        }
      }));
      memo = { time: Date.now(), items: result };
      setItems(result);
      setTime(memo.time);
    } finally { clearTimeout(limit); setBusy(false); }
  }
  useEffect(() => { void refresh(false); }, []);
  return <div>
    <div className="page-heading"><div><div className="eyebrow">GITHUB / LEITURA PÚBLICA</div>
      <h1>Fontes GitHub</h1><p>Consulta pontual às issues públicas. Não substitui o plano de controle dos computadores.</p>
    </div><button className="btn btn-primary" disabled={busy} onClick={() => void refresh(true)}>
      <RefreshCcw size={16}/>{busy ? 'Consultando...' : 'Atualizar agora'}
    </button></div>
    <div className="banner banner-notice"><ShieldAlert size={19}/><div>
      <strong>Sem permissão de execução</strong>
      <span>Não usa credenciais nem comandos. A situação das issues não valida SHA, runner, sessão, Gateway, lease ou custo. TODO Global no Notion permanece privado.</span>
    </div></div>
    <section className="panel">
      <div className="panel-head"><div><h2>Estado público por fonte</h2>
        <p>{time ? 'Consultado em ' + date(new Date(time).toISOString()) : 'Consulta ainda pendente'} · cache de 5 minutos por navegação</p>
      </div><GitBranch size={19}/></div>
      <div className="source-readonly-list">
        {items.map(x => <div className="source-readonly-item" key={x.target.repository + '/' + x.target.issue}>
          <div><strong>{x.target.label}</strong>
            <p>{x.target.repository} · Issue #{x.target.issue}</p>
            {x.title && <p>{x.title}</p>}
            {x.error ? <small className="source-error"><AlertCircle size={13}/>{x.error}</small> :
              <small><Clock3 size={13}/> Atualizada em {date(x.updated)} · lida em {date(x.checked)}</small>}
          </div>
          <div className="source-readonly-right">
            <span className={'tag ' + (x.state === 'open' ? 'tag-warning' : x.state === 'closed' ? 'tag-good' : 'tag-danger')}>
              {x.state === 'open' ? 'Issue aberta' : x.state === 'closed' ? 'Issue fechada' : 'Indisponível'}
            </span>
            <a target="_blank" rel="noreferrer"
              href={'https://github.com/ericson-j-santos/' + x.target.repository + '/issues/' + x.target.issue}>Abrir fonte</a>
          </div>
        </div>)}
      </div>
    </section>
    <div className="source-disclaimer"><ShieldAlert size={17}/>
      Mesmo com cinco issues fechadas, ready_for_work permanece falso e E2E físico continua não comprovado até recibos independentes.
      A API pública limita chamadas sem autenticação; ausência de resposta nunca vira sucesso.
    </div>
  </div>;
}
