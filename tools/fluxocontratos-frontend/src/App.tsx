import { useEffect, useMemo, useState } from 'react';
import { auth, api } from '@appdeploy/client';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  CloudDownload,
  Code2,
  Download,
  FileCheck2,
  FileText,
  Fingerprint,
  History,
  Layers,
  ListChecks,
  Lock,
  LogOut,
  Menu,
  Plus,
  RefreshCw,
  Save,
  Search,
  Settings,
  ShieldCheck,
  ShieldOff,
  Upload,
  X,
} from 'lucide-react';

type Lote = {
  id: string;
  inicio: number;
  fim: number;
  quantidade: number;
  origem: string;
  destino: string;
  responsavel: string;
  chave: string;
  concluidos: number;
  sucesso: number;
  falha: number;
  contOrigem: number;
  contInterno: number;
  contPublicado: number;
  retry: number;
  fase: string;
  estado: string;
  bloqueio: string;
  checkpoint: string;
  sha: string;
  evidencia: string;
  readback: string;
  log: string;
  rollback: string;
  proximaAcao: string;
  revisao: string;
  revision: number;
  criadoEm: string;
  atualizadoEm: string;
  historico: Evento[];
};
type Evento = {
  em: string;
  tipo: string;
  antes: string;
  depois: string;
  responsavel: string;
  evidencia: string;
  rollback?: string;
};
type Script = {
  id: string;
  nome: string;
  tipo: string;
  sha: string;
  descricao: string;
  em: string;
  verificado: boolean;
  executado: boolean;
};
type Config = {
  revision: number;
  limiteLote: number;
  paralelismo: number;
  retriesMax: number;
  backoffSeg: number;
  dlq: boolean;
  integridade: boolean;
  autoExecutar: boolean;
};
const BASE: Config = {
  revision: 0,
  limiteLote: 500,
  paralelismo: 2,
  retriesMax: 3,
  backoffSeg: 5,
  dlq: true,
  integridade: true,
  autoExecutar: false,
};
const FASES = [
  ['ENTRADA', 'Entrada'],
  ['PREFLIGHT', 'Pré-verificação'],
  ['DOWNLOAD', 'Download'],
  ['CONFERENCIA', 'Conferência'],
  ['UPLOAD', 'Upload interno'],
  ['PUBLICACAO', 'Publicação'],
  ['VALIDACAO', 'Validação independente'],
  ['REPLAY', 'Retomada segura'],
  ['ENCERRAMENTO', 'Encerramento'],
];
const ESTADOS = [
  'PLANEJADO',
  'EM_ANDAMENTO',
  'FALHA_VALIDACAO',
  'ERRO_TRANSITORIO',
  'ERRO_DEFINITIVO',
  'ACAO_HUMANA',
  'BLOQUEADO',
  'EVIDENCIA_DECLARADA',
  'ENCERRADO',
];
const BLOQUEIOS = [
  'NENHUM',
  'INTEGRACAO_AUSENTE',
  'VALIDACAO',
  'TRANSITORIO',
  'DEFINITIVO',
  'HUMANO',
  'CUSTO',
  'EVIDENCIA',
];
const traducao = (x: string) =>
  (
    ({
      PLANEJADO: 'Planejado',
      EM_ANDAMENTO: 'Em andamento',
      FALHA_VALIDACAO: 'Falha de validação',
      ERRO_TRANSITORIO: 'Erro transitório',
      ERRO_DEFINITIVO: 'Erro definitivo',
      ACAO_HUMANA: 'Ação humana',
      BLOQUEADO: 'Bloqueado',
      EVIDENCIA_DECLARADA: 'Evidência declarada',
      ENCERRADO: 'Encerrado',
      INTEGRACAO_AUSENTE: 'Integração ausente',
      VALIDACAO: 'Falha de validação',
      TRANSITORIO: 'Erro transitório',
      DEFINITIVO: 'Erro definitivo',
      HUMANO: 'Ação humana',
      CUSTO: 'Custo incerto',
      EVIDENCIA: 'Prova insuficiente',
      NENHUM: 'Nenhum',
    }) as Record<string, string>
  )[x] || x;
const fmt = (n: number) => new Intl.NumberFormat('pt-BR').format(n || 0);
const hora = (s?: string) => (s ? new Date(s).toLocaleString('pt-BR') : '—');
const chaveNova = () => 'op_' + crypto.randomUUID().replace(/-/g, '');
const erroApi = (e: unknown) => {
  const a = e as {
    response?: { data?: { error?: string; message?: string } };
    message?: string;
  };
  return (
    a.response?.data?.error ||
    a.response?.data?.message ||
    a.message ||
    'Falha não comprovada. Atualize antes de repetir.'
  );
};
function arquivo(
  nome: string,
  conteudo: string,
  tipo = 'text/plain;charset=utf-8'
) {
  const b = new Blob([conteudo], { type: tipo });
  const u = URL.createObjectURL(b);
  const a = document.createElement('a');
  a.href = u;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(u), 500);
}
function Chip({
  children,
  tone = 'gray',
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return (
    <span className={'chip ' + tone}>
      <span className="dot" />
      {children}    </span>
  );
}
function Campo({ children }: { children: React.ReactNode }) {
  return <label className="label">{children}</label>;
}
function App() {
  const [user, setUser] = useState<{
    userId: string;
    name?: string;
    email?: string;
  } | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [tab, setTab] = useState('painel');
  const [mobileMenu, setMobileMenu] = useState(false);
  const [lotes, setLotes] = useState<Lote[]>([]);
  const [scripts, setScripts] = useState<Script[]>([]);
  const [config, setConfig] = useState<Config>(BASE);
  const [cursor, setCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('TODOS');
  const [novo, setNovo] = useState(false);
  const [criar, setCriar] = useState({
    inicio: 1,
    fim: 500,
    origem: '',
    destino: '',
    responsavel: '',
    chave: chaveNova(),
  });
  const [selected, setSelected] = useState<Lote | null>(null);
  const [edit, setEdit] = useState<Partial<Lote> & { confirmacao: string }>({
    confirmacao: '',
  });
  const [history, setHistory] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [sha, setSha] = useState('');
  const [expected, setExpected] = useState('');
  const [descricao, setDescricao] = useState('');

  useEffect(() => {
    auth
      .getUser()
      .then(u => {
        setUser(u);
        setAuthLoading(false);
      })
      .catch(e => {
        setError(erroApi(e));
        setAuthLoading(false);
      });
  }, []);
  useEffect(() => {
    if (user) void reload();
  }, [user]);
  async function reload() {
    setBusy(true);
    setError('');
    try {
      const [a, b, c] = await Promise.all([
        api.get('/api/lotes'),
        api.get('/api/scripts'),
        api.get('/api/config'),
      ]);
      setLotes(a.data.items || []);
      setCursor(a.data.cursor || null);
      setScripts(b.data.items || []);
      setConfig(c.data.item || BASE);
    } catch (e) {
      setError(erroApi(e));
    } finally {
      setBusy(false);
    }
  }
  async function more() {
    if (!cursor) return;
    setBusy(true);
    try {
      const a = await api.get(
        '/api/lotes?cursor=' + encodeURIComponent(cursor)
      );
      setLotes(v => [...v, ...a.data.items]);
      setCursor(a.data.cursor || null);
    } catch (e) {
      setError(erroApi(e));
    } finally {
      setBusy(false);
    }
  }
  const planned = useMemo(
    () => lotes.reduce((a, l) => a + l.quantidade, 0),
    [lotes]
  );
  const declared = useMemo(
    () => lotes.reduce((a, l) => a + l.concluidos, 0),
    [lotes]
  );
  const approved = useMemo(
    () =>
      lotes
        .filter(l => l.estado === 'ENCERRADO')
        .reduce((a, l) => a + l.concluidos, 0),
    [lotes]
  );
  const failed = useMemo(() => lotes.reduce((a, l) => a + l.falha, 0), [lotes]);
  const blocked = lotes.filter(l =>
    ['BLOQUEADO', 'ERRO_DEFINITIVO', 'ACAO_HUMANA', 'FALHA_VALIDACAO'].includes(
      l.estado
    )
  ).length;
  const list = lotes.filter(
    l =>
      (filter === 'TODOS' || l.estado === filter) &&
      [l.id, l.origem, l.destino, l.responsavel]
        .join(' ')
        .toLowerCase()
        .includes(search.toLowerCase())
  );
  const rate = (100 * approved) / 110000;
  function notify(s: string) {
    setError('');
    setOk(s);
  }
  function open(l: Lote) {
    setSelected(l);
    setEdit({ ...l, confirmacao: '' });
    setHistory(false);
  }
  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      if (criar.fim - criar.inicio + 1 > config.limiteLote)
        throw Error(
          'Limite configurado de ' + fmt(config.limiteLote) + ' por lote.'
        );
      const r = await api.post('/api/lotes', criar);
      const x = r.data.item as Lote;
      setLotes(v =>
        v.some(y => y.id === x.id)
          ? v.map(y => (y.id === x.id ? x : y))
          : [x, ...v]
      );
      setNovo(false);
      setTab('lotes');
      notify(
        r.data.criado
          ? 'Planejamento persistido. Nenhum arquivo foi processado.'
          : 'Repetição detectada: nenhum lote duplicado.'
      );
      setCriar(v => ({
        ...v,
        inicio: v.fim + 1,
        fim: v.fim + config.limiteLote,
        chave: chaveNova(),
      }));
    } catch (e) {
      setError(erroApi(e));
    } finally {
      setBusy(false);
    }
  }
  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || busy) return;
    setBusy(true);
    setError('');
    try {
      const r = await api.put(
        '/api/lotes/' + encodeURIComponent(selected.id),
        edit
      );
      const x = r.data.item as Lote;
      setLotes(v => v.map(y => (y.id === x.id ? x : y)));
      setSelected(x);
      setEdit({ ...x, confirmacao: '' });
      notify(
        'Ficha gravada e relida. Não constitui prova física independente.'
      );
    } catch (e) {
      setError(erroApi(e));
    } finally {
      setBusy(false);
    }
  }
  async function saveConfig(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.put('/api/config', config);
      setConfig(r.data.item);
      notify('Limites gravados. Execução externa permanece desligada.');
    } catch (e) {
      setError(erroApi(e));
    } finally {      setBusy(false);
    }
  }
  async function fileChanged(f: File | null) {
    setFile(null);
    setSha('');
    if (!f) return;
    if (!/\.(sh|py)$/i.test(f.name) || f.size > 1024 * 1024) {
      setError('Somente arquivo .sh/.py de até 1 MB.');
      return;
    }
    try {
      const dig = await crypto.subtle.digest('SHA-256', await f.arrayBuffer());
      setSha(
        Array.from(new Uint8Array(dig))
          .map(x => x.toString(16).padStart(2, '0'))
          .join('')
      );
      setFile(f);
    } catch (e) {
      setError(erroApi(e));
    }
  }
  async function register(e: React.FormEvent) {
    e.preventDefault();
    if (!file || expected !== sha || busy) return;
    setBusy(true);
    try {
      const r = await api.post('/api/scripts', {
        nome: file.name,
        tipo: file.name.endsWith('.sh') ? 'SH' : 'PYTHON',
        sha,
        esperado: expected,
        descricao,
      });
      setScripts(v =>
        v.some(x => x.id === r.data.item.id) ? v : [r.data.item, ...v]
      );
      setFile(null);
      setSha('');
      setExpected('');
      setDescricao('');
      const input = document.getElementById(
        'scriptfile'
      ) as HTMLInputElement | null;
      if (input) input.value = '';
      notify('SHA registrado. Arquivo não enviado nem executado.');
    } catch (e) {
      setError(erroApi(e));
    } finally {
      setBusy(false);
    }
  }
  function report() {
    const lines = [
      'RELATÓRIO PARA REVISÃO — HOMOLOGAÇÃO',
      'Data: ' + new Date().toLocaleString('pt-BR'),
      'Meta aproximada: 110.000 contratos',
      'Lotes carregados: ' +
        fmt(lotes.length) +
        (cursor ? ' (AMOSTRA PARCIAL)' : ''),
      'Planejados: ' + fmt(planned),
      'Concluídos declarados: ' + fmt(declared),
      'Encerramentos registrados: ' + fmt(approved),
      'Falhas: ' + fmt(failed),
      'Origem / interno / publicação declarados: ' + fmt(lotes.reduce((a,l)=>a+(l.contOrigem||0),0))+' / '+fmt(lotes.reduce((a,l)=>a+(l.contInterno||0),0))+' / '+fmt(lotes.reduce((a,l)=>a+(l.contPublicado||0),0)),
      'Bloqueios: ' + fmt(blocked),
      'Comprovação física: NÃO VERIFICADA',
      'Custo adicional autorizado: R$ 0,00',
      'Sem envio automático, contratos individuais ou credenciais.',
    ];
    arquivo(
      'relatorio-lotes.eml',
      'MIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\nSubject: Relatorio contratos legados\r\n\r\n' +
        lines.join('\r\n'),
      'message/rfc822;charset=utf-8'
    );
    notify('Relatório .eml baixado. Nenhum e-mail foi enviado.');
  }
  const sections = [
    ['painel', 'Visão geral', Layers],
    ['lotes', 'Fila de lotes', ClipboardList],
    ['fluxo', 'Etapas e controles', ListChecks],
    ['scripts', 'Scripts e limites', Code2],
    ['dlq', 'Fila de falhas (DLQ)', AlertTriangle],
    ['historico', 'Histórico e evidências', History],
  ] as const;
  const nav = (key: string) => {
    setTab(key);
    setMobileMenu(false);
    setError('');
    setOk('');
  };
  if (authLoading)
    return (
      <div className="center">
        <ShieldCheck size={30} /> Validando acesso...
      </div>
    );
  if (!user)
    return (
      <div className="login">
        <div className="login-panel">
          <span className="login-mark">
            <FileCheck2 size={27} />
          </span>
          <p className="eyebrow">CENTRAL OPERACIONAL · HOMOLOGAÇÃO</p>
          <h1>Contratos legados, sob controle.</h1>
          <p>
            Gerencie registros, provas e bloqueios de lotes sem conectar ou
            modificar servidores corporativos.
          </p>
          <div className="login-info">
            <Lock size={17} /> Acesso autenticado. Dados de cada usuário
            permanecem separados.
          </div>
          <button
            className="primary wide"
            onClick={() =>
              auth.signInWithRedirect().catch(e => setError(erroApi(e)))
            }
          >
            Entrar com segurança <ArrowRight size={18} />
          </button>
          {error && <div className="error">{error}</div>}
          <small>Não informe senhas nem dados pessoais nesta central.</small>
        </div>
      </div>
    );
  return (
    <div className="app">
      <aside className={'side ' + (mobileMenu ? 'show' : '')}>
        <div className="brand">
          <span className="brand-icon">
            <FileCheck2 size={22} />
          </span>
          <span>
            <strong>FluxoContratos</strong>
            <small>OPERATIONS CENTER</small>
          </span>
        </div>
        <div className="environment">
          <span className="dot" /> AMBIENTE DE HOMOLOGAÇÃO
        </div>
        <div className="nav-caption">ESPAÇO DE TRABALHO</div>
        <nav aria-label="Navegação">
          {sections.map(([id, title, Icon]) => (
            <button
              key={id}
              className={tab === id ? 'active' : ''}
              onClick={() => nav(id)}
            >
              <Icon size={18} />
              {title}
              {tab === id && <ChevronRight size={15} />}
            </button>
          ))}
        </nav>
        <div className="side-foot">
          <div className="side-safe">
            <ShieldCheck size={19} />
            <b>Modo protegido</b>
            <p>Sem Docker, execução física ou publicação automática.</p>
            <small>Custo adicional: R$ 0,00</small>
          </div>
          <div className="account">
            <span className="avatar">
              {(user.name || user.email || 'U')[0]}
            </span>
            <span>
              <b>{user.name || 'Operador'}</b>
              <small>{user.email || 'Conta autenticada'}</small>
            </span>
            <button
              title="Sair"
              aria-label="Sair"
              onClick={() =>
                auth.signOut().then(() => {
                  setUser(null);
                  setLotes([]);
                })
              }
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>
      {mobileMenu && (
        <div className="scrim" onClick={() => setMobileMenu(false)} />
      )}
      <div className="work">
        <header className="header">
          <div>
            <button
              className="hamburger"
              aria-label="Abrir menu"
              onClick={() => setMobileMenu(true)}
            >
              <Menu size={20} />            </button>
            <span>Operações</span>
            <ChevronRight size={15} />
            <b>{sections.find(x => x[0] === tab)?.[1]}</b>
          </div>
          <div>
            <span className="secure">
              <ShieldCheck size={15} /> Sem execução externa
            </span>
            <button
              aria-label="Atualizar dados"
              title="Atualizar dados"
              onClick={reload}
            >
              <RefreshCw size={18} />
            </button>
            <span className="avatar">
              {(user.name || user.email || 'U')[0]}
            </span>
          </div>
        </header>
        <main className="content">
          {error && (
            <div className="message error" role="alert">
              <AlertTriangle size={18} />
              <span>{error}</span>
              <button aria-label="Fechar aviso" onClick={() => setError('')}>
                <X size={16} />
              </button>
            </div>
          )}
          {ok && (
            <div className="message good" role="status">
              <CheckCircle2 size={18} />
              <span>{ok}</span>
              <button aria-label="Fechar mensagem" onClick={() => setOk('')}>
                <X size={16} />
              </button>
            </div>
          )}
          {tab === 'painel' && (
            <>
              <div className="heading">
                <div>
                  <p className="eyebrow">
                    PAINEL OPERACIONAL / VISÃO CONSOLIDADA
                  </p>
                  <h1>Controle de contratos legados</h1>
                  <p>Da origem ao destino, cada etapa com rastreabilidade.</p>
                </div>
                <div className="actions">
                  <button className="secondary" onClick={report}>
                    <Download size={16} /> Exportar relatório
                  </button>
                  <button className="primary" onClick={() => setNovo(true)}>
                    <Plus size={18} /> Novo lote
                  </button>
                </div>
              </div>
              <div className="banner">
                <CircleHelp size={19} />
                <div>
                  <b>Integrações físicas ainda não conectadas.</b>
                  <p>
                    Os números refletem registros desta central. A meta de 110
                    mil é estimada; encerramento declarado não equivale a
                    comprovação operacional.
                  </p>
                </div>
                <button onClick={() => nav('fluxo')}>
                  Ver controles <ArrowRight size={16} />
                </button>
              </div>
              <div className="kpis">
                {[
                  ['Legado estimado', '110.000', 'Meta não auditada', FileText],
                  [
                    'Planejados',
                    fmt(planned),
                    fmt(lotes.length) + ' lotes carregados',
                    Layers,
                  ],
                  [
                    'Encerramentos registrados',
                    fmt(approved),
                    'Prova externa indisponível',
                    CheckCircle2,
                  ],
                  [
                    'Pendências críticas',
                    fmt(blocked),
                    fmt(failed) + ' falhas registradas',
                    AlertTriangle,
                  ],
                ].map(([title, value, subtitle, Icon], i) => (
                  <div className="kpi" key={String(title)}>
                    <div>
                      <span>{String(title)}</span>
                      <span className={'kpi-icon c' + i}>
                        <Icon size={20} />
                      </span>
                    </div>
                    <strong>{String(value)}</strong>
                    <small>{String(subtitle)}</small>
                  </div>
                ))}
              </div>
              <div className="dashboard-grid">
                <section className="card">
                  <div className="card-head">
                    <div>
                      <h2>Progresso do legado</h2>
                      <p>Registros encerrados em relação ao total estimado</p>
                    </div>
                    <Chip tone="amber">Não validado fisicamente</Chip>
                  </div>
                  <div className="progress">
                    <strong>
                      {rate.toLocaleString('pt-BR', {
                        maximumFractionDigits: 2,
                      })}
                      <span>%</span>
                    </strong>
                    <p>
                      {fmt(approved)} de 110.000 com encerramento registrado
                      {cursor ? ' · amostra parcial' : ''}
                    </p>
                    <div
                      className="track"
                      role="progressbar"
                      aria-label="Percentual de encerramentos registrados"
                      aria-valuenow={Math.min(rate, 100)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      <div style={{ width: Math.min(rate, 100) + '%' }} />
                    </div>
                    <div className="progress-note">
                      <span>Comprovação independente</span>
                      <b>Indisponível</b>
                    </div>
                  </div>
                  <div className="triple">
                    <div>
                      <small>Planejados</small>
                      <strong>{fmt(planned)}</strong>
                    </div>
                    <div>
                      <small>Concluídos declarados</small>
                      <strong>{fmt(declared)}</strong>
                    </div>
                    <div>
                      <small>Falhas</small>
                      <strong>{fmt(failed)}</strong>
                    </div>
                  </div>
                </section>
                <section className="card">
                  <div className="card-head">
                    <div>
                      <h2>Integridade operacional</h2>
                      <p>Proteções exigidas</p>
                    </div>
                    <ShieldCheck size={20} color="#189e8b" />
                  </div>
                  <div className="integrity">
                    {[
                      [
                        'SHA-256 e idempotência',
                        'Identidade do arquivo e chave por lote',
                        true,
                        Fingerprint,
                      ],
                      [
                        'Checkpoint e histórico',
                        'Retomada e registro antes/depois',
                        true,
                        History,
                      ],
                      [
                        'Execução nos servidores',
                        'Sem ligação aos sistemas externos',
                        false,
                        ShieldOff,
                      ],
                      [
                        'Publicação definitiva',
                        'Requer autorização específica',
                        false,
                        Upload,
                      ],
                    ].map(([a, b, yes, Icon]) => (
                      <div key={String(a)}>
                        <span className={yes ? 'green-icon' : 'warn-icon'}>
                          <Icon size={17} />
                        </span>
                        <span>
                          <b>{String(a)}</b>
                          <small>{String(b)}</small>
                        </span>                        <Chip tone={yes ? 'blue' : 'amber'}>
                          {yes ? 'Exigido' : 'Bloqueado'}
                        </Chip>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
              <section className="card">
                <div className="card-head">
                  <div>
                    <h2>Fila de processamento</h2>
                    <p>Últimos lotes visíveis e suas ações</p>
                  </div>
                  <button className="textbtn" onClick={() => nav('lotes')}>
                    Ver fila completa <ArrowRight size={16} />
                  </button>
                </div>
                <Queue lotes={lotes.slice(0, 5)} onOpen={open} />
              </section>
            </>
          )}
          {tab === 'lotes' && (
            <>
              <div className="heading">
                <div>
                  <p className="eyebrow">EXECUÇÃO CONTROLADA / LOTES</p>
                  <h1>Fila de processamento</h1>
                  <p>
                    Planeje, registre provas, classifique falhas e prepare a
                    retomada.
                  </p>
                </div>
                <div className="actions">
                  <button className="secondary" onClick={report}>
                    <Download size={16} /> Relatório
                  </button>
                  <button className="primary" onClick={() => setNovo(true)}>
                    <Plus size={18} /> Adicionar lote
                  </button>
                </div>
              </div>
              <div className="inline-stats">
                <b>{lotes.length}</b> lotes carregados <b>{fmt(planned)}</b>{' '}
                planejados <b>{fmt(declared)}</b> declarados{' '}
                {cursor && <Chip tone="amber">Página parcial</Chip>}
              </div>
              <section className="card">
                <div className="toolbar">
                  <div className="search">
                    <Search size={17} />
                    <input
                      aria-label="Buscar lote"
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                      placeholder="Buscar por lote, origem ou responsável"
                    />
                  </div>
                  <select
                    aria-label="Filtrar estado"
                    value={filter}
                    onChange={e => setFilter(e.target.value)}
                  >
                    <option value="TODOS">Todos os estados</option>
                    {ESTADOS.map(x => (
                      <option key={x} value={x}>
                        {traducao(x)}
                      </option>
                    ))}
                  </select>
                </div>
                <Queue lotes={list} onOpen={open} />
                <div className="table-foot">
                  <span>
                    {list.length} registros exibidos · valores apenas dos lotes
                    carregados
                  </span>
                  {cursor && (
                    <button
                      className="secondary small"
                      disabled={busy}
                      onClick={more}
                    >
                      Carregar mais
                    </button>
                  )}
                </div>
              </section>
              <p className="footnote">
                <Lock size={15} /> Intervalos exatos não são duplicados.
                Verificação global de sobreposições exige índice no executor
                futuro.
              </p>
            </>
          )}
          {tab === 'fluxo' && (
            <>
              <div className="heading">
                <div>
                  <p className="eyebrow">CONTROLE DE PROCESSO</p>
                  <h1>Fluxo guiado, com portas de segurança</h1>
                  <p>
                    Cada fase precisa de prova antes de ser considerada
                    concluída.
                  </p>
                </div>
                <Chip tone="amber">Execução desligada</Chip>
              </div>
              <div className="steps">
                {FASES.map(([id, name], i) => (
                  <article className="step" key={id}>
                    <div>
                      <span>{String(i + 1).padStart(2, '0')}</span>
                      <ArrowRight size={17} />
                    </div>
                    <h3>{name}</h3>
                    <p>
                      {
                        [
                          'Registro seguro e identificação do lote',
                          'Pré-verificação somente leitura do servidor Linux',
                          'Download em lotes com limite de capacidade',
                          'SHA-256 e regras de negócio antes de avançar',
                          'Transferência para ambiente interno autorizado',
                          'Autorização expressa antes de publicar',
                          'Leitura independente no destino',
                          'Repetição sem efeitos duplicados',
                          'Registro, evidência, rollback e revisão',
                        ][i]
                      }
                    </p>
                    <small>Prova externa pendente</small>
                  </article>
                ))}
              </div>
              <div className="columns">
                <section className="card padded">
                  <h2>Classificação das ocorrências</h2>
                  {[
                    [
                      'Fato comprovado',
                      'Evidência no destino e leitura independente',
                    ],
                    [
                      'Erro transitório',
                      'Tentativas com espera crescente até limite',
                    ],
                    ['Erro definitivo', 'Bloqueio e fila de falhas (DLQ)'],
                    ['Ação humana', 'Aprovação explícita registrada'],
                    [
                      'Diagnóstico sem efeito',
                      'Não altera percentual aprovado',
                    ],
                    [
                      'Ação efetiva',
                      'Mudança, antes/depois e evidência de efeito',
                    ],
                  ].map(([a, b]) => (
                    <div className="guide" key={a}>
                      <b>{a}</b>
                      <span>{b}</span>
                    </div>
                  ))}
                </section>
                <section className="card padded">
                  <h2>Portas de aprovação obrigatórias</h2>
                  {[
                    'Preflight físico Linux, CPU, RAM e disco',
                    'Validação de origem, destino e permissões',
                    'SHA-256 e integridade dos PDFs',
                    'Checkpoint persistente e idempotência',
                    'Permissão específica para publicação',
                    'Teste de replay, rollback e leitura externa',
                  ].map(x => (
                    <div className="gate" key={x}>
                      <ShieldOff size={16} />
                      <span>{x}</span>
                      <b>Pendente</b>
                    </div>
                  ))}
                </section>
              </div>
            </>
          )}
          {tab === 'scripts' && (
            <>
              <div className="heading">
                <div>
                  <p className="eyebrow">AUTOMAÇÃO GOVERNADA</p>
                  <h1>Scripts e limites seguros</h1>
                  <p>
                    Guarde configurações e identidades SHA sem executar código.
                  </p>
                </div>
                <Chip tone="amber">Sem processamento ativo</Chip>
              </div>
              <div className="columns">
                <section className="card padded">
                  <h2>Limites de processamento</h2>
                  <p className="sub">Estas opções não ativam o processador.</p>                  <form onSubmit={saveConfig}>
                    <div className="formgrid">
                      {[
                        ['limiteLote', 'Contratos por lote', 1, 2000],
                        ['paralelismo', 'Processos paralelos', 1, 4],
                        ['retriesMax', 'Tentativas máximas', 0, 6],
                        ['backoffSeg', 'Espera inicial (segundos)', 1, 300],
                      ].map(([key, label, min, max]) => (
                        <div key={String(key)}>
                          <Campo>{String(label)}</Campo>
                          <input
                            type="number"
                            required
                            min={Number(min)}
                            max={Number(max)}
                            value={Number(config[key as keyof Config])}
                            onChange={e =>
                              setConfig(v => ({
                                ...v,
                                [String(key)]: Number(e.target.value),
                              }))
                            }
                          />
                        </div>
                      ))}
                    </div>
                    <div className="safelist">
                      <p>
                        <Check size={15} /> Fila de erros (DLQ): obrigatória
                      </p>
                      <p>
                        <Check size={15} /> Integridade de arquivos: obrigatória
                      </p>
                      <p>
                        <Lock size={15} /> Execução automática: desativada
                      </p>
                    </div>
                    <button disabled={busy} className="primary" type="submit">
                      <Save size={16} /> Salvar parâmetros
                    </button>
                  </form>
                </section>
                <section className="card padded">
                  <h2>Registrar versão de script</h2>
                  <p className="sub">
                    O arquivo não é enviado ao servidor; só o resumo SHA-256 é
                    cadastrado.
                  </p>
                  <form onSubmit={register}>
                    <div>
                      <Campo>Selecione o arquivo .sh ou .py</Campo>
                      <input
                        id="scriptfile"
                        type="file"
                        accept=".sh,.py"
                        onChange={e =>
                          void fileChanged(e.target.files?.[0] || null)
                        }
                      />
                    </div>
                    <div>
                      <Campo>SHA-256 oficial esperado</Campo>
                      <input
                        maxLength={64}
                        value={expected}
                        onChange={e =>
                          setExpected(e.target.value.toLowerCase().trim())
                        }
                        placeholder="Hash esperado de 64 caracteres"
                      />
                    </div>
                    <div>
                      <Campo>SHA-256 calculado no navegador</Campo>
                      <input
                        readOnly
                        value={sha}
                        placeholder="Selecione um arquivo para conferir"
                      />
                    </div>
                    <div>
                      {sha && sha === expected ? (
                        <Chip tone="green">Identidade correspondente</Chip>
                      ) : (
                        <Chip tone="amber">Pendente ou divergente</Chip>
                      )}
                    </div>
                    <div>
                      <Campo>Descrição da versão</Campo>
                      <textarea
                        rows={2}
                        value={descricao}
                        onChange={e => setDescricao(e.target.value)}
                        placeholder="Ambiente, finalidade e origem da versão"
                      />
                    </div>
                    <button
                      className="primary"
                      disabled={!file || !sha || sha !== expected || busy}
                      type="submit"
                    >
                      <Fingerprint size={16} /> Cadastrar versão verificada
                    </button>
                  </form>
                </section>
              </div>
              <section className="card">
                <div className="card-head">
                  <div>
                    <h2>Scripts registrados</h2>
                    <p>
                      Somente identidades de arquivo; nenhum script é executado.
                    </p>
                  </div>
                  <div className="actions">
                    <button
                      className="secondary small"
                      onClick={() =>
                        arquivo(
                          'modelo.sh',
                          '#!/usr/bin/env bash\nset -Eeuo pipefail\necho "BLOQUEADO: sem preflight ou autorização para execução real."\nexit 78\n'
                        )
                      }
                    >
                      Modelo .sh <Download size={15} />
                    </button>
                    <button
                      className="secondary small"
                      onClick={() =>
                        arquivo(
                          'modelo.py',
                          '#!/usr/bin/env python3\n"""Modelo seguro. Nenhuma transferência é autorizada."""\nprint("BLOQUEADO: execução real indisponível.")\nraise SystemExit(78)\n'
                        )
                      }
                    >
                      Modelo Python <Download size={15} />
                    </button>
                  </div>
                </div>
                {scripts.length ? (
                  <div className="script-list">
                    {scripts.map(x => (
                      <div key={x.id}>
                        <Code2 size={20} />
                        <div>
                          <b>{x.nome}</b>
                          <small>
                            SHA-256: {x.sha.slice(0, 24)}… · {hora(x.em)}
                          </small>
                          <span>{x.descricao || 'Sem descrição'}</span>
                        </div>
                        <Chip tone="green">Hash conferido</Chip>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Empty text="Nenhuma versão cadastrada ainda." />
                )}
              </section>
            </>
          )}
          {tab === 'dlq' && (
            <>
              <div className="heading">
                <div>
                  <p className="eyebrow">TRATAMENTO DE FALHAS / DLQ</p>
                  <h1>Fila de falhas definitivas</h1>
                  <p>Registros que exigem correção ou intervenção humana antes de qualquer retomada.</p>
                </div>
                <Chip tone="amber">Sem replay automático</Chip>
              </div>
              <div className="banner"><AlertTriangle size={19}/><div><b>Quarentena lógica de acompanhamento.</b><p>Aqui aparecem lotes classificados como falha definitiva ou falha de validação. A fila técnica real dependerá da integração ao executor Linux.</p></div></div>
              <section className="card"><div className="card-head"><div><h2>Ocorrências aguardando análise</h2><p>Responsável, próxima ação e evidência obrigatórios na ficha</p></div><Chip tone="red">{lotes.filter(l=>['ERRO_DEFINITIVO','FALHA_VALIDACAO'].includes(l.estado)).length} lotes</Chip></div>
                <Queue lotes={lotes.filter(l=>['ERRO_DEFINITIVO','FALHA_VALIDACAO'].includes(l.estado))} onOpen={open}/>
              </section>
              {cursor&&<p className="footnote">Há mais páginas. Esta fila exibe somente os lotes carregados.</p>}
            </>
          )}
          {tab === 'historico' && (
            <>
              <div className="heading">
                <div>
                  <p className="eyebrow">RASTREABILIDADE</p>
                  <h1>Histórico e evidências</h1>
                  <p>
                    Registros auditáveis do que foi declarado, antes/depois e
                    responsável.
                  </p>
                </div>
                <button className="secondary" onClick={report}>
                  <Download size={16} /> Exportar resumo
                </button>
              </div>
              <div className="banner">
                <ShieldCheck size={19} />
                <div>
                  <b>
                    Provas declaradas não são testemunho externo autenticado.
                  </b>
                  <p>
                    A leitura independente nos servidores corporativos continua                    bloqueada sem integração autorizada.
                  </p>
                </div>
              </div>
              <section className="card">
                <div className="card-head">
                  <div>
                    <h2>Linha do tempo</h2>
                    <p>
                      Últimos eventos dos lotes carregados; histórico limitado
                      por lote
                    </p>
                  </div>
                </div>
                {lotes
                  .flatMap(l => l.historico.map(e => ({ ...e, lote: l.id })))
                  .sort((a, b) => b.em.localeCompare(a.em))
                  .slice(0, 60)
                  .map((x, i) => (
                    <div className="event" key={x.lote + x.em + i}>
                      <span className="event-icon">
                        <History size={16} />
                      </span>
                      <div>
                        <b>
                          {x.lote} <Chip tone="blue">{traducao(x.tipo)}</Chip>
                        </b>
                        <p>
                          {x.antes} → {x.depois}
                        </p>
                        <small>
                          Responsável: {x.responsavel} · Evidência:{' '}
                          {x.evidencia}
                        </small>
                      </div>
                      <time>{hora(x.em)}</time>
                    </div>
                  ))}
                {!lotes.length && (
                  <Empty text="O histórico aparecerá depois de cadastrar o primeiro lote." />
                )}
              </section>
            </>
          )}
          <footer>
            <span>
              <ShieldCheck size={15} /> Homologação · LGPD · Custo adicional R$
              0,00
            </span>
            <span>Regras 1.6.21 · SHA 58dcd420 · Sem publicação real</span>
          </footer>
        </main>
      </div>
      {novo && (
        <div className="backdrop" onClick={() => setNovo(false)}>
          <div
            className="modal compact"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-title"
            onClick={e => e.stopPropagation()}
          >
            <div className="modal-top">
              <div>
                <p className="eyebrow">PLANEJAMENTO SEGURO</p>
                <h2 id="create-title">Novo lote</h2>
              </div>
              <button aria-label="Fechar" onClick={() => setNovo(false)}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={create}>
              {error && <div className="message error" role="alert"><AlertTriangle size={16}/><span>{error}</span></div>}
              <div className="formbody">
                <div className="formgrid">
                  <div>
                    <Campo>Contrato inicial</Campo>
                    <input
                      type="number"
                      min="1"
                      required
                      value={criar.inicio}
                      onChange={e =>
                        setCriar(v => ({
                          ...v,
                          inicio: Number(e.target.value),
                        }))
                      }
                    />
                  </div>
                  <div>
                    <Campo>Contrato final</Campo>
                    <input
                      type="number"
                      min={criar.inicio}
                      required
                      value={criar.fim}
                      onChange={e =>
                        setCriar(v => ({ ...v, fim: Number(e.target.value) }))
                      }
                    />
                  </div>
                </div>
                <div className="hint">
                  Quantidade: {fmt(Math.max(0, criar.fim - criar.inicio + 1))} ·
                  Máximo configurado: {fmt(config.limiteLote)}
                </div>
                <div>
                  <Campo>Origem sem credenciais</Campo>
                  <input
                    required
                    maxLength={160}
                    value={criar.origem}
                    onChange={e =>
                      setCriar(v => ({ ...v, origem: e.target.value }))
                    }
                    placeholder="Servidor externo / unidade"
                  />
                </div>
                <div>
                  <Campo>Destino previsto</Campo>
                  <input
                    required
                    maxLength={160}
                    value={criar.destino}
                    onChange={e =>
                      setCriar(v => ({ ...v, destino: e.target.value }))
                    }
                    placeholder="Servidor interno / sistema"
                  />
                </div>
                <div>
                  <Campo>Responsável</Campo>
                  <input
                    required
                    maxLength={100}
                    value={criar.responsavel}
                    onChange={e =>
                      setCriar(v => ({ ...v, responsavel: e.target.value }))
                    }
                  />
                </div>
                <p className="hint">
                  <Fingerprint size={15} /> Chave única preservada em reenvios.
                  Sem download de PDFs.
                </p>
              </div>
              <div className="modal-actions">
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setNovo(false)}
                >
                  Cancelar
                </button>
                <button className="primary" disabled={busy} type="submit">
                  Cadastrar planejamento <ArrowRight size={16} />
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {selected && (
        <div className="backdrop" onClick={() => setSelected(null)}>
          <div
            className="modal detail"
            role="dialog"
            aria-modal="true"
            aria-labelledby="lot-title"
            onClick={e => e.stopPropagation()}
          >
            <div className="modal-top">
              <div>
                <p className="eyebrow">
                  LOTE GOVERNADO · VERSÃO {selected.revision}
                </p>
                <h2 id="lot-title">{selected.id}</h2>
                <p>
                  {fmt(selected.quantidade)} contratos previstos ·{' '}
                  {selected.origem} → {selected.destino}
                </p>
              </div>
              <button aria-label="Fechar" onClick={() => setSelected(null)}>
                <X size={20} />
              </button>
            </div>
            <div className="tabs">
              <button
                className={!history ? 'active' : ''}
                onClick={() => setHistory(false)}
              >
                Atualizar registro
              </button>
              <button
                className={history ? 'active' : ''}
                onClick={() => setHistory(true)}
              >
                Histórico antes/depois
              </button>            </div>
            {history ? (
              <div className="formbody">
                {selected.historico
                  .slice()
                  .reverse()
                  .map((x, i) => (
                    <div className="history-entry" key={i}>
                      <small>
                        {hora(x.em)} · {x.responsavel}
                      </small>
                      <p>
                        <b>Antes:</b> {x.antes}
                      </p>
                      <p>
                        <b>Depois:</b> {x.depois}
                      </p>
                      <p>
                        <b>Evidência:</b> {x.evidencia}
                      </p>
                      <p>
                        <b>Rollback:</b> {x.rollback || '—'}
                      </p>
                    </div>
                  ))}
              </div>
            ) : (
              <form onSubmit={save}>
                {error && <div className="message error" role="alert"><AlertTriangle size={16}/><span>{error}</span></div>}
                <div className="formbody">
                  <p className="hint">
                    Esta ficha não executa o processo corporativo nem publica
                    contratos.
                  </p>
                  <div className="formgrid">
                    <div>
                      <Campo>Etapa</Campo>
                      <select
                        value={edit.fase || 'ENTRADA'}
                        onChange={e =>
                          setEdit(v => ({ ...v, fase: e.target.value }))
                        }
                      >
                        {FASES.map(([id, title]) => (
                          <option key={id} value={id}>
                            {title}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <Campo>Estado</Campo>
                      <select
                        value={edit.estado || 'PLANEJADO'}
                        onChange={e =>
                          setEdit(v => ({ ...v, estado: e.target.value }))
                        }
                      >
                        {ESTADOS.map(x => (
                          <option key={x} value={x}>
                            {traducao(x)}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <Campo>Concluídos declarados</Campo>
                      <input
                        type="number"
                        min="0"
                        max={selected.quantidade}
                        value={edit.concluidos ?? 0}
                        onChange={e =>
                          setEdit(v => ({
                            ...v,
                            concluidos: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Campo>Sucessos</Campo>
                      <input
                        type="number"
                        min="0"
                        max={selected.quantidade}
                        value={edit.sucesso ?? 0}
                        onChange={e =>
                          setEdit(v => ({
                            ...v,
                            sucesso: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Campo>Falhas</Campo>
                      <input
                        type="number"
                        min="0"
                        max={selected.quantidade}
                        value={edit.falha ?? 0}
                        onChange={e =>
                          setEdit(v => ({
                            ...v,
                            falha: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Campo>Retentativas</Campo>
                      <input
                        type="number"
                        min="0"
                        value={edit.retry ?? 0}
                        onChange={e =>
                          setEdit(v => ({
                            ...v,
                            retry: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Campo>Tipo de bloqueio</Campo>
                      <select
                        value={edit.bloqueio || 'INTEGRACAO_AUSENTE'}
                        onChange={e =>
                          setEdit(v => ({ ...v, bloqueio: e.target.value }))
                        }
                      >
                        {BLOQUEIOS.map(x => (
                          <option key={x} value={x}>
                            {traducao(x)}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <Campo>Próxima revisão</Campo>
                      <input
                        type="date"
                        value={edit.revisao || ''}
                        onChange={e =>
                          setEdit(v => ({ ...v, revisao: e.target.value }))
                        }
                      />
                    </div>
                  </div>
                  <div className="formgrid">
                    {[
                      ['contOrigem','Arquivos encontrados na origem'],
                      ['contInterno','Arquivos conferidos no servidor interno'],
                      ['contPublicado','Arquivos encontrados no sistema final']
                    ].map(([key,title])=><div key={key}>
                      <Campo>{title} (declarado)</Campo>
                      <input type="number" min="0" max={selected.quantidade}
                        value={Number(edit[key as keyof Lote]??0)}
                        onChange={e=>setEdit(v=>({...v,[key]:Number(e.target.value)}))}/>
                    </div>)}
                  </div>
                  <p className="hint">Reconciliação declarada: origem, interno e publicado devem coincidir após validação externa. Este painel não consulta os servidores.</p>
                  {[
                    ['checkpoint', 'Checkpoint durável (referência externa)'],
                    ['evidencia', 'Evidência e resultado antes/depois'],
                    ['sha', 'SHA-256 da versão'],
                    ['readback', 'Leitura independente no destino'],
                    ['log', 'Log sanitizado'],
                    ['proximaAcao', 'Próxima ação executável'],
                    ['responsavel', 'Responsável'],
                    ['rollback', 'Plano de retorno (rollback)'],
                  ].map(([key, title]) => (
                    <div key={key}>
                      <Campo>{title}</Campo>
                      <input
                        required={[
                          'checkpoint',
                          'evidencia',
                          'proximaAcao',
                          'responsavel',
                          'rollback',
                        ].includes(key)}
                        maxLength={key === 'sha' ? 64 : 500}
                        value={String(edit[key as keyof Lote] || '')}
                        onChange={e =>
                          setEdit(v => ({ ...v, [key]: e.target.value }))
                        }
                        placeholder={
                          key === 'sha'
                            ? '64 caracteres hexadecimais'
                            : key === 'readback'
                              ? 'Obrigatório para encerramento'
                              : undefined
                        }
                      />
                    </div>
                  ))}
                  {(edit.fase === 'PUBLICACAO' ||
                    edit.fase === 'ENCERRAMENTO' ||                    edit.estado === 'ENCERRADO') && (
                    <div className="danger">
                      <b>Confirmação explícita obrigatória</b>
                      <p>
                        Registra apenas uma declaração. Não publica contratos
                        nem executa alterações externas.
                      </p>
                      <code>
                        {edit.fase === 'ENCERRAMENTO' ||
                        edit.estado === 'ENCERRADO'
                          ? 'CONFIRMAR ENCERRAMENTO'
                          : 'CONFIRMAR PUBLICACAO'}
                      </code>
                      <input
                        aria-label="Confirmação"
                        value={edit.confirmacao}
                        onChange={e =>
                          setEdit(v => ({ ...v, confirmacao: e.target.value }))
                        }
                        placeholder="Digite a expressão acima"
                      />
                    </div>
                  )}
                </div>
                <div className="modal-actions">
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setSelected(null)}
                  >
                    Cancelar
                  </button>
                  <button type="submit" className="primary" disabled={busy}>
                    <Save size={16} /> Guardar e conferir
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="empty">
      <ClipboardList size={29} />
      <b>Nenhum registro</b>
      <p>{text}</p>
    </div>
  );
}
function Queue({
  lotes,
  onOpen,
}: {
  lotes: Lote[];
  onOpen: (x: Lote) => void;
}) {
  return !lotes.length ? (
    <Empty text="Cadastre o primeiro planejamento para iniciar a fila." />
  ) : (
    <div className="tablewrap">
      <table>
        <thead>
          <tr>
            <th>Lote / intervalo</th>
            <th>Estado</th>
            <th>Progresso</th>
            <th>Responsável</th>
            <th>Próxima ação</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {lotes.map(l => (
            <tr key={l.id}>
              <td>
                <b>{l.id.replaceAll('_', ' ')}</b>
                <small>
                  {fmt(l.inicio)} a {fmt(l.fim)} · {fmt(l.quantidade)} PDFs
                </small>
              </td>
              <td>
                <Chip
                  tone={
                    l.estado === 'ENCERRADO'
                      ? 'green'
                      : l.estado === 'BLOQUEADO' ||
                          l.estado === 'ERRO_DEFINITIVO'
                        ? 'red'
                        : 'gray'
                  }
                >
                  {traducao(l.estado)}
                </Chip>
                <small>{FASES.find(x => x[0] === l.fase)?.[1]}</small>
              </td>
              <td>
                <div className="percent">
                  <b>{Math.round((l.concluidos / l.quantidade) * 100)}%</b>
                  <span>
                    {fmt(l.concluidos)}/{fmt(l.quantidade)}
                  </span>
                </div>
                <div className="tinytrack">
                  <div
                    style={{ width: (l.concluidos / l.quantidade) * 100 + '%' }}
                  />
                </div>
              </td>
              <td>{l.responsavel}</td>
              <td className="next">{l.proximaAcao}</td>
              <td>
                <button
                  className="open"
                  aria-label={'Abrir ' + l.id}
                  onClick={() => onOpen(l)}
                >
                  <ChevronRight size={19} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export default App;
