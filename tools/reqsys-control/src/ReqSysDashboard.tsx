import { useEffect, useMemo, useState } from 'react';
import PublicGithubReadOnly from './PublicGithubReadOnly';
import {
  AlertCircle,
  ArrowRight,
  ArrowUpRight,
  Ban,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  CloudOff,
  Database,
  Download,
  ExternalLink,
  FileCheck2,
  FileClock,
  FileText,
  Filter,
  GitBranch,
  History,
  House,
  Info,
  Laptop2,
  Layers3,
  ListChecks,
  LockKeyhole,
  Menu,
  Monitor,
  MoreHorizontal,
  Plus,
  RefreshCcw,
  Search,
  Server,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Upload,
  X,
  Zap,
} from 'lucide-react';

type Page = 'overview' | 'queue' | 'hosts' | 'history' | 'e2e' | 'sources' | 'rules';
type GateState = 'nao_verificado' | 'declarado' | 'falhou';
type Category =
  | 'runner'
  | 'admissao'
  | 'dependencia'
  | 'configuracao'
  | 'continuidade';
type Priority = 'P0' | 'P1' | 'P2';
type DemandState = 'BLOQUEADA' | 'AGUARDANDO' | 'EM_ANALISE' | 'PREPARADA';
type Host = {
  id: string;
  name: string;
  model: string;
  role: string;
  source: string;
  labels: string[];
  version: string;
  sha: string;
  blocker: string;
  category: Category;
  human: boolean;
  lastCheck: string;
  gates: Record<string, GateState>;
};
type Demand = {
  id: string;
  title: string;
  project: string;
  repo: string;
  reference: string;
  url: string;
  priority: Priority;
  state: DemandState;
  kind: string;
  host: string;
  sha: string;
  dependencies: string;
  cost: string;
  required: string;
  next: string;
  category: Category;
  human: boolean;
  source: string;
  owner: string;
};
type Recheck = {
  id: string;
  host: string;
  when: string;
  sha: string;
  source: string;
  note: string;
  category: Category;
  human: boolean;
  gates: Record<string, GateState>;
};
type Evidence = {
  id: string;
  demand: string;
  title: string;
  url: string;
  sha: string;
  type: string;
  when: string;
  author: string;
};
type Flow = {
  first: string;
  second: string;
  request: string;
  sha: string;
  checkpoint: string;
  lease: boolean;
  replay: boolean;
  validator: string;
  readback: string;
  negative: boolean;
};
type Snapshot = {
  demands: Demand[];
  hosts: Host[];
  history: Recheck[];
  evidences: Evidence[];
  flow: Flow;
};

const GATES = [
  ['identity', 'Identidade física'],
  ['labels', 'Versão e labels'],
  ['normal', 'Perfil NORMAL'],
  ['sha', 'SHA admitido'],
  ['launch', 'SESSION_LAUNCH_OK'],
  ['gateway', 'Command Gateway'],
  ['worktree', 'Worktree exclusivo'],
  ['lease', 'Lease exclusivo'],
  ['native', 'Dependências nativas'],
  ['runner', 'Runner disponível'],
  ['cost', 'Custo incremental zero'],
] as const;
const CATEGORIES: Category[] = [
  'runner',
  'admissao',
  'dependencia',
  'configuracao',
  'continuidade',
];
const CAT: Record<Category, string> = {
  runner: 'Runner',
  admissao: 'Admissão',
  dependencia: 'Dependência',
  configuracao: 'Configuração',
  continuidade: 'Continuidade entre hosts',
};
const STATE: Record<DemandState, string> = {
  BLOQUEADA: 'Bloqueada',
  AGUARDANDO: 'Aguardando',
  EM_ANALISE: 'Em análise',
  PREPARADA: 'Preparação documental',
};
const pSort: Record<Priority, number> = { P0: 0, P1: 1, P2: 2 };
const emptyGates = () =>
  Object.fromEntries(GATES.map(g => [g[0], 'nao_verificado'])) as Record<
    string,
    GateState
  >;
const initialFlow: Flow = {
  first: '',
  second: '',
  request: '',
  sha: '',
  checkpoint: '',
  lease: false,
  replay: false,
  validator: '',
  readback: '',
  negative: false,
};

const INITIAL_HOSTS: Host[] = [
  {
    id: 'desktop',
    name: 'DESKTOP-PDQK954',
    model: 'Desktop PC24x7 · identidade a revalidar',
    role: 'Runtime preferencial',
    source: 'desktop-pc24x7-runtime',
    labels: ['pc24x7 (esperada)', 'desktop-runtime (esperada)'],
    version: 'Não revalidada',
    sha: '',
    blocker:
      'Readiness atual não comprovado; Broker/runner precisam de readback',
    category: 'configuracao',
    human: false,
    lastCheck: '',
    gates: emptyGates(),
  },
  {
    id: 'lenovo',
    name: 'DESKTOP-RP23OGS',
    model: 'Lenovo 10T8A03G00 · i5-8500T',
    role: 'Host de continuidade',
    source: 'desktop-pc24x7-runtime',
    labels: ['labels atuais pendentes'],
    version: 'Não revalidada',
    sha: '',
    blocker: 'Pickup histórico não prova retomada da mesma tarefa',
    category: 'continuidade',
    human: false,
    lastCheck: '',
    gates: emptyGates(),
  },
  {
    id: 'noteri',
    name: 'Noteri',
    model: 'Notebook Windows / WSL2 · identidade a revalidar',
    role: 'Host alternativo',
    source: 'noteri-runtime',
    labels: ['perfil NORMAL pendente'],
    version: 'Não revalidada',
    sha: '',
    blocker: 'Gateway/journal e dependências nativas exigem verificação atual',
    category: 'dependencia',
    human: true,
    lastCheck: '',
    gates: emptyGates(),
  },
  {
    id: 'optiplex',
    name: 'Dell OptiPlex 7080',
    model: 'Micro · i9-10900T · 64 GB',
    role: 'Candidato IA local',
    source: 'inventário, não telemetria',
    labels: ['sem certificação de runner'],
    version: 'Não revalidada',
    sha: '',
    blocker: 'Não existe certificação de sessão/worker neste painel',
    category: 'admissao',
    human: false,
    lastCheck: '',
    gates: emptyGates(),
  },
];

const INITIAL_DEMANDS: Demand[] = [
  {
    id: 'D-001',
    title: 'Certificar continuidade E2E física entre computadores',
    project: 'E2E Platform',
    repo: 'ericson-j-santos/e2e-platform',
    reference: 'Issue #10',
    url: 'https://github.com/ericson-j-santos/e2e-platform/issues/10',
    priority: 'P0',
    state: 'BLOQUEADA',
    kind: 'E2E físico · dois hosts',
    host: 'desktop',
    sha: '',
    dependencies:
      'Dois hosts físicos, checkpoint CAS, lease, Validator independente',
    cost: 'Não comprovado',
    required:
      'Request ID, checkpoint/hash, leases, pickup A/B, caso negativo, readback',
    next: 'Revalidar Desktop e segundo host por canal somente leitura',
    category: 'continuidade',
    human: false,
    source: 'Referência histórica da issue; exige readback atual',
    owner: 'Runtime Platform',
  },
  {
    id: 'D-002',
    title: 'Recuperar prontidão nativa do Desktop Admin Broker',
    project: 'ReqSys / Runtime',
    repo: 'ericson-j-santos/reqsys-v2-enterprise-real',
    reference: 'Issue #3096',
    url: 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3096',
    priority: 'P0',
    state: 'BLOQUEADA',
    kind: 'Diagnóstico e preparação',
    host: 'desktop',
    sha: '',
    dependencies:
      'Readback do plano de controle, versão do runner e dependências nativas',
    cost: 'Não comprovado',
    required: 'Diagnóstico, bloqueio raiz, fonte e SHA, inspeção independente',
    next: 'Ler estado atual do Broker sem alteração administrativa',
    category: 'configuracao',
    human: false,
    source: 'Referência histórica; não implica incidente atual confirmado',
    owner: 'Runtime Platform',
  },
  {
    id: 'D-003',
    title: 'Qualificar ciclo real do agente Llama/Ollama',
    project: 'Engineering Control Plane',
    repo: 'ericson-j-santos/engineering-orchestrator',
    reference: 'Fluxo de agente local',
    url: 'https://github.com/ericson-j-santos/engineering-orchestrator',
    priority: 'P0',
    state: 'AGUARDANDO',
    kind: 'Builder + Validator',
    host: 'optiplex',
    sha: '',
    dependencies:
      'Modelo local, host NORMAL, checkpoint CAS, PR draft única e readback',
    cost: 'Não comprovado',
    required:
      'Testes real/negativo, patch SHA-bound, Validator e replay idempotente',
    next: 'Conferir admissão e host disponível antes de preparar a execução',
    category: 'admissao',
    human: false,
    source: 'Planejamento inicial; sem admissão vigente',
    owner: 'Engineering Control Plane',
  },
  {
    id: 'D-004',
    title: 'Validar TRANSF-009 no checkout Linux real',
    project: 'Transferidor Documental',
    repo: 'ericson-j-santos/transferidor-documental',
    reference: 'Issue #3',
    url: 'https://github.com/ericson-j-santos/transferidor-documental/issues/3',
    priority: 'P1',
    state: 'AGUARDANDO',
    kind: 'Testes/E2E Linux DEV',
    host: 'noteri',
    sha: '',
    dependencies:
      'Dois servidores Linux autorizados e dados exclusivamente sintéticos',
    cost: 'Não comprovado',
    required:
      'Sintaxe, negativo, replay, SHA-256, regressão, Validator e readback',
    next: 'Confirmar checkout real e capacidade nativa Linux sem executar transporte',
    category: 'dependencia',
    human: false,
    source: 'Referência da issue; ambiente real não validado',
    owner: 'Transferidor Documental',
  },
  {
    id: 'D-005',
    title: 'Qualificar Transferidor v0.4.0 em NTFS',
    project: 'Noteri Runtime',
    repo: 'ericson-j-santos/noteri-runtime',
    reference: 'Issue #83',
    url: 'https://github.com/ericson-j-santos/noteri-runtime/issues/83',
    priority: 'P1',
    state: 'BLOQUEADA',
    kind: 'E2E NTFS sintético DEV',
    host: 'noteri',
    sha: '',
    dependencies: 'Origem imutável, perfil NORMAL, Gateway e pacote íntegro',
    cost: 'Não comprovado',
    required: 'SHA-256 de pacote, casos negativos, E2E e readback independente',
    next: 'Inspecionar integridade da origem e gate NORMAL sem mutações',
    category: 'admissao',
    human: false,
    source: 'Referência histórica; readiness não verificado agora',
    owner: 'Noteri Runtime',
  },
];

const KEYS = 'reqsys-control-center-v1';
function load(): Snapshot {
  const base: Snapshot = {
    demands: INITIAL_DEMANDS,
    hosts: INITIAL_HOSTS,
    history: [],
    evidences: [],
    flow: initialFlow,
  };
  try {
    const raw = localStorage.getItem(KEYS);
    if (!raw) return base;
    const value = JSON.parse(raw);
    if (
      !value ||
      !Array.isArray(value.demands) ||
      !Array.isArray(value.history) ||
      !Array.isArray(value.evidences)
    )
      return base;
    const hosts = INITIAL_HOSTS.map(h => {
      const saved = Array.isArray(value.hosts)
        ? value.hosts.find((a: Host) => a && a.id === h.id)
        : null;
      return saved
        ? {
            ...h,
            lastCheck:
              typeof saved.lastCheck === 'string' ? saved.lastCheck : '',
            gates: { ...emptyGates(), ...saved.gates },
          }
        : h;
    });
    return {
      demands: value.demands.filter(
        (d: Demand) =>
          d && typeof d.id === 'string' && typeof d.title === 'string'
      ),
      hosts,
      history: value.history.filter(
        (r: Recheck) =>
          r && typeof r.id === 'string' && typeof r.host === 'string'
      ),
      evidences: value.evidences.filter(
        (e: Evidence) =>
          e && typeof e.id === 'string' && typeof e.title === 'string'
      ),
      flow:
        value.flow && typeof value.flow === 'object'
          ? { ...initialFlow, ...value.flow }
          : initialFlow,
    };
  } catch {
    return base;
  }
}
function fmt(iso: string) {
  if (!iso) return 'Sem verificação atual';
  try {
    return new Date(iso).toLocaleString('pt-BR', {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  } catch {
    return 'Data inválida';
  }
}
function safeUrl(url: string) {
  return /^https:\/\/[a-z0-9.-]+(?:\/|$)/i.test(url.trim()) ? url.trim() : '';
}
function shortSha(sha: string) {
  return sha ? sha.slice(0, 12) : 'Não admitido';
}
function id(prefix: string) {
  return (
    prefix +
    '-' +
    Date.now().toString(36) +
    '-' +
    Math.random().toString(36).slice(2, 6)
  );
}
function Tone({ state }: { state: DemandState }) {
  return (
    <span className={'pill pill-' + state.toLowerCase()}>
      <span className="dot" />
      {STATE[state] || 'Pendente'}
    </span>
  );
}
function Badge({
  children,
  tone = 'neutral',
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={'tag tag-' + tone}>{children}</span>;
}

const MenuItems: { id: Page; label: string; icon: typeof House }[] = [
  { id: 'overview', label: 'Visão geral', icon: House },
  { id: 'queue', label: 'Fila de demandas', icon: ListChecks },
  { id: 'hosts', label: 'Prontidão dos hosts', icon: Server },
  { id: 'history', label: 'Revalidações', icon: History },
  { id: 'e2e', label: 'Fluxo E2E', icon: GitBranch },
  { id: 'sources', label: 'Fontes GitHub', icon: RefreshCcw },
  { id: 'rules', label: 'Governança', icon: ShieldCheck },
];
const blankDraft = (): Demand => ({
  id: '',
  title: '',
  project: 'ReqSys',
  repo: '',
  reference: '',
  url: '',
  priority: 'P1',
  state: 'AGUARDANDO',
  kind: 'Inspeção somente leitura',
  host: 'desktop',
  sha: '',
  dependencies: '',
  cost: 'Não comprovado',
  required: '',
  next: '',
  category: 'admissao',
  human: false,
  source: 'Cadastro manual não verificado',
  owner: '',
});

function App() {
  const [data, setData] = useState<Snapshot>(load);
  const [page, setPage] = useState<Page>('overview');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedDemand, setSelectedDemand] = useState<string>('D-001');
  const [hostSelection, setHostSelection] = useState<string>('desktop');
  const [query, setQuery] = useState('');
  const [priority, setPriority] = useState('Todas');
  const [stateFilter, setStateFilter] = useState('Todos');
  const [modal, setModal] = useState<
    null | 'demand' | 'recheck' | 'evidence' | 'import'
  >(null);
  const [draft, setDraft] = useState<Demand>(blankDraft);
  const [rHost, setRHost] = useState('desktop');
  const [rGates, setRGates] = useState<Record<string, GateState>>(emptyGates);
  const [rSource, setRSource] = useState('');
  const [rNote, setRNote] = useState('');
  const [rSha, setRSha] = useState('');
  const [rCategory, setRCategory] = useState<Category>('runner');
  const [rHuman, setRHuman] = useState(false);
  const [ev, setEv] = useState<Evidence>({
    id: '',
    demand: 'D-001',
    title: '',
    url: '',
    sha: '',
    type: 'Observação manual',
    when: '',
    author: '',
  });
  const [notice, setNotice] = useState('');
  const [importText, setImportText] = useState('');
  const [storageFailed, setStorageFailed] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(KEYS, JSON.stringify(data));
      setStorageFailed(false);
    } catch {
      setStorageFailed(true);
    }
  }, [data]);

  const selected =
    data.demands.find(d => d.id === selectedDemand) || data.demands[0];
  const selectedHost =
    data.hosts.find(h => h.id === hostSelection) || data.hosts[0];
  const sorted = useMemo(
    () =>
      data.demands
        .filter(d => {
          const hay = [
            d.title,
            d.project,
            d.repo,
            d.reference,
            d.next,
            d.kind,
            d.owner,
          ]
            .join(' ')
            .toLowerCase();
          return (
            hay.includes(query.toLowerCase()) &&
            (priority === 'Todas' || d.priority === priority) &&
            (stateFilter === 'Todos' || d.state === stateFilter)
          );
        })
        .sort(
          (a, b) =>
            pSort[a.priority] - pSort[b.priority] || a.id.localeCompare(b.id)
        ),
    [data.demands, query, priority, stateFilter]
  );
  const blocked = data.demands.filter(d => d.state === 'BLOQUEADA').length;
  const gatesCount = (h: Host) =>
    GATES.filter(g => h.gates[g[0]] === 'declarado').length;
  const flow = data.flow;
  const flowValid = Boolean(
    flow.first &&
    flow.second &&
    flow.first !== flow.second &&
    flow.request.trim() &&
    /^[a-f0-9]{40}$/i.test(flow.sha.trim()) &&
    /^[a-f0-9]{64}$/i.test(flow.checkpoint.trim()) &&
    flow.lease &&
    flow.replay &&
    safeUrl(flow.validator) &&
    safeUrl(flow.readback) &&
    flow.negative
  );
  const flowInputs = [
    Boolean(flow.first),
    Boolean(flow.second && flow.first !== flow.second),
    Boolean(flow.request.trim()),
    /^[a-f0-9]{40}$/i.test(flow.sha.trim()),
    /^[a-f0-9]{64}$/i.test(flow.checkpoint.trim()),
    flow.lease,
    flow.replay,
    Boolean(safeUrl(flow.validator)),
    Boolean(safeUrl(flow.readback)),
    flow.negative,
  ];

  function notify(message: string) {
    setNotice(message);
    window.setTimeout(() => setNotice(''), 5000);
  }
  function openDemand(item?: Demand) {
    setDraft(item ? { ...item } : blankDraft());
    setModal('demand');
  }
  function saveDemand(e: React.FormEvent) {
    e.preventDefault();
    if (
      draft.title.trim().length < 5 ||
      !/^[-\w]+\/[-\w.]+$/.test(draft.repo.trim()) ||
      !draft.next.trim() ||
      !draft.required.trim()
    ) {
      notify(
        'Informe título, repositório owner/repo, evidências exigidas e próxima ação.'
      );
      return;
    }
    if (draft.sha.trim() && !/^[a-f0-9]{40}$/i.test(draft.sha.trim())) {
      notify('SHA deve conter 40 caracteres hexadecimais ou ficar vazio.');
      return;
    }
    const cleaned = {
      ...draft,
      title: draft.title.trim(),
      repo: draft.repo.trim(),
      url: safeUrl(draft.url),
      sha: draft.sha.trim(),
      id: draft.id || id('D'),
      source: 'Registro manual; validação externa pendente',
    };
    setData(v => ({
      ...v,
      demands: draft.id
        ? v.demands.map(d => (d.id === draft.id ? cleaned : d))
        : [...v.demands, cleaned],
    }));
    setSelectedDemand(cleaned.id);
    setModal(null);
    notify('Demanda salva localmente. Sem autorização de execução.');
  }
  function openRecheck(host = 'desktop') {
    setRHost(host);
    setRGates(emptyGates());
    setRSource('');
    setRNote('');
    setRSha('');
    setRCategory('runner');
    setRHuman(false);
    setModal('recheck');
  }
  function saveRecheck(e: React.FormEvent) {
    e.preventDefault();
    if (rSource.trim().length < 8 || rNote.trim().length < 8) {
      notify(
        'Indique fonte identificável e observação de pelo menos 8 caracteres.'
      );
      return;
    }
    if (rSha.trim() && !/^[a-f0-9]{40}$/i.test(rSha.trim())) {
      notify('SHA inválido: use 40 caracteres ou deixe vazio.');
      return;
    }
    const now = new Date().toISOString();
    const record: Recheck = {
      id: id('RV'),
      host: rHost,
      when: now,
      sha: rSha.trim(),
      source: rSource.trim(),
      note: rNote.trim(),
      category: rCategory,
      human: rHuman,
      gates: { ...rGates },
    };
    setData(v => ({
      ...v,
      history: [record, ...v.history],
      hosts: v.hosts.map(h =>
        h.id === rHost
          ? {
              ...h,
              lastCheck: now,
              gates: { ...rGates },
              category: rCategory,
              human: rHuman,
              blocker: rNote.trim(),
              sha: rSha.trim(),
            }
          : h
      ),
    }));
    setModal(null);
    setPage('history');
    notify(
      'Revalidação documental registrada; ready_for_work permanece FALSE.'
    );
  }
  function openEvidence(demand?: string) {
    setEv({
      id: '',
      demand: demand || selectedDemand || data.demands[0]?.id || '',
      title: '',
      url: '',
      sha: '',
      type: 'Observação manual',
      when: '',
      author: '',
    });
    setModal('evidence');
  }
  function saveEvidence(e: React.FormEvent) {
    e.preventDefault();
    if (ev.title.trim().length < 6 || !safeUrl(ev.url)) {
      notify('Informe descrição e URL HTTPS válida.');
      return;
    }
    if (ev.sha.trim() && !/^[a-f0-9]{40}$/i.test(ev.sha.trim())) {
      notify('SHA inválido: são necessários 40 caracteres.');
      return;
    }
    setData(v => ({
      ...v,
      evidences: [
        {
          ...ev,
          id: id('EV'),
          when: new Date().toISOString(),
          url: safeUrl(ev.url),
        },
        ...v.evidences,
      ],
    }));
    setModal(null);
    notify('Evidência catalogada; não foi validada independentemente.');
  }
  function exportData() {
    const blob = new Blob(
      [
        JSON.stringify(
          {
            schema: 'reqsys-control-center-v1',
            exportedAt: new Date().toISOString(),
            ...data,
          },
          null,
          2
        ),
      ],
      { type: 'application/json' }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'reqsys-painel-registros.json';
    a.click();
    URL.revokeObjectURL(url);
    notify('Backup JSON exportado do navegador.');
  }
  function importData(e: React.FormEvent) {
    e.preventDefault();
    if (importText.length > 1024 * 1024) {
      notify('Arquivo acima do limite de 1 MB.');
      return;
    }
    try {
      const raw = JSON.parse(importText);
      if (
        raw.schema !== 'reqsys-control-center-v1' ||
        !Array.isArray(raw.demands) ||
        !Array.isArray(raw.history) ||
        !Array.isArray(raw.evidences)
      )
        throw new Error('Esquema inválido');
      if (
        raw.demands.length > 300 ||
        raw.history.length > 1000 ||
        raw.evidences.length > 1000
      )
        throw new Error('Registros acima do limite');
      if (
        !raw.demands.every(
          (d: Demand) =>
            d &&
            typeof d.id === 'string' &&
            typeof d.title === 'string' &&
            typeof d.repo === 'string' &&
            d.id.length < 100 &&            d.title.length < 500 &&
            ['P0', 'P1', 'P2'].includes(d.priority)
        )
      )
        throw new Error('Demanda inválida');
      if (
        !raw.history.every(
          (r: Recheck) =>
            r &&
            typeof r.id === 'string' &&
            typeof r.host === 'string' &&
            INITIAL_HOSTS.some(h => h.id === r.host)
        )
      )
        throw new Error('Revalidação inválida');
      if (
        !raw.evidences.every(
          (x: Evidence) =>
            x &&
            typeof x.id === 'string' &&
            typeof x.title === 'string' &&
            typeof x.url === 'string' &&
            Boolean(safeUrl(x.url))
        )
      )
        throw new Error('Evidência inválida');
      setData(v => {
        const merge = <T extends { id: string }>(a: T[], b: T[]) => {
          const ids = new Set(a.map(x => x.id));
          return [...a, ...b.filter(x => !ids.has(x.id))];
        };
        return {
          ...v,
          demands: merge(v.demands, raw.demands),
          history: merge(v.history, raw.history),
          evidences: merge(v.evidences, raw.evidences),
        };
      });
      setModal(null);
      setImportText('');
      notify(
        'Registros mesclados sem duplicar IDs. Gates dos hosts não foram importados.'
      );
    } catch (err) {
      notify(
        'Importação bloqueada: ' +
          (err instanceof Error ? err.message : 'JSON inválido')
      );
    }
  }
  function setFlow<K extends keyof Flow>(key: K, value: Flow[K]) {
    setData(v => ({ ...v, flow: { ...v.flow, [key]: value } }));
  }
  function navigate(next: Page) {
    setPage(next);
    setSidebarOpen(false);
  }

  return (
    <div className="app-frame">
      <aside className={'sidebar ' + (sidebarOpen ? 'sidebar-open' : '')}>
        <div className="brand">
          <div className="brand-symbol">
            <Layers3 size={21} strokeWidth={2.5} />
          </div>
          <div>
            <div className="brand-name">
              ReqSys <span>Control</span>
            </div>
            <div className="brand-sub">CENTRO OPERACIONAL</div>
          </div>
          <button
            className="mobile-close"
            aria-label="Fechar menu"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={18} />
          </button>
        </div>
        <div className="sidebar-section">WORKSPACE</div>
        <nav className="side-nav">
          {MenuItems.map(item => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={'nav-item ' + (page === item.id ? 'active' : '')}
                onClick={() => navigate(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
                {item.id === 'queue' && (
                  <span className="nav-count">{data.demands.length}</span>
                )}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-shield">
            <ShieldCheck size={19} />
            <div>
              <strong>Modo protegido</strong>
              <small>Somente leitura e registro</small>
            </div>
          </div>
          <div className="side-separator" />
          <div className="sidebar-foot">
            <span className="live-dot" />
            <span>Sem conexão com hosts</span>
          </div>
          <div className="sidebar-version">Regras v1.6.20 · main@86abe65b</div>
        </div>
      </aside>
      {sidebarOpen && (
        <button
          className="sidebar-scrim"
          aria-label="Fechar menu"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <main className="main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="menu-toggle"
              aria-label="Abrir menu"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu size={21} />
            </button>
            <span className="breadcrumb">ReqSys</span>
            <ChevronRight size={15} className="muted" />
            <span className="breadcrumb-current">
              {MenuItems.find(x => x.id === page)?.label}
            </span>
          </div>
          <div className="topbar-actions">
            <span className="mode-badge">
              <LockKeyhole size={13} /> Fail-closed ativo
            </span>
            <button
              className="icon-btn"
              title="Exportar registros JSON"
              onClick={exportData}
            >
              <Download size={18} />
            </button>
            <button
              className="btn btn-primary top-new"
              onClick={() => openDemand()}
            >
              <Plus size={17} /> Nova demanda
            </button>
          </div>
        </header>
        <div className="content">
          {notice && (
            <div className="toast" role="status">
              <Info size={16} />
              {notice}
              <button aria-label="Fechar aviso" onClick={() => setNotice('')}>
                <X size={14} />
              </button>
            </div>
          )}
          {storageFailed && (
            <div className="banner banner-danger">
              <AlertCircle size={17} /> Armazenamento local indisponível.
              Exporte os registros antes de fechar a página.
            </div>
          )}
          {page === 'overview' && (
            <>
              <div className="page-heading overview-heading">
                <div>
                  <div className="eyebrow">OPERAÇÃO · DEV / E2E</div>
                  <h1>Visão operacional</h1>
                  <p>
                    Uma visão sobre o que está pendente, o que foi observado e o
                    que pode ser preparado com segurança.
                  </p>
                </div>
                <div className="heading-buttons">
                  <button
                    className="btn btn-secondary"
                    onClick={() => openRecheck()}
                  >
                    <RefreshCcw size={16} /> Registrar revalidação
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={() => navigate('queue')}
                  >
                    Abrir fila <ArrowRight size={16} />
                  </button>
                </div>
              </div>
              <div className="banner banner-notice">
                <ShieldAlert size={20} />
                <div>
                  <strong>Sem certificação operacional em tempo real</strong>
                  <span>
                    Este site usa registros locais e referências históricas.
                    Nenhum host é habilitado sem evidência externa atual e
                    verificação independente.
                  </span>
                </div>
                <button onClick={() => navigate('rules')}>
                  Política <ArrowUpRight size={14} />
                </button>
              </div>
              <div className="metrics-grid">
                <div className="metric">
                  <div className="metric-top">
                    <span>Demandas na fila</span>
                    <ListChecks size={19} />
                  </div>
                  <div className="metric-number">
                    {data.demands.length.toString().padStart(2, '0')}
                  </div>
                  <div className="metric-bottom">
                    <span className="micro-dot teal" />{' '}
                    {data.demands.filter(d => d.priority === 'P0').length}{' '}
                    prioridades P0
                  </div>
                </div>
                <div className="metric">
                  <div className="metric-top">
                    <span>Demandas bloqueadas</span>
                    <Ban size={19} />
                  </div>
                  <div className="metric-number">
                    {blocked.toString().padStart(2, '0')}
                  </div>
                  <div className="metric-bottom">
                    <span className="micro-dot orange" /> Exigem verificação ou
                    desbloqueio
                  </div>
                </div>
                <div className="metric">
                  <div className="metric-top">
                    <span>Hosts aptos agora</span>
                    <Monitor size={19} />
                  </div>
                  <div className="metric-number">
                    00
                    <span className="metric-total"> / {data.hosts.length}</span>
                  </div>
                  <div className="metric-bottom">
                    <span className="micro-dot red" /> Sem autorização
                    verificável
                  </div>
                </div>
                <div className="metric">
                  <div className="metric-top">
                    <span>Revalidações registradas</span>
                    <History size={19} />
                  </div>
                  <div className="metric-number">
                    {data.history.length.toString().padStart(2, '0')}
                  </div>
                  <div className="metric-bottom">
                    <span className="micro-dot blue" /> Registro não equivale a
                    aceite
                  </div>
                </div>
              </div>
              <div className="overview-grid">
                <section className="panel queue-preview">
                  <div className="panel-head">
                    <div>
                      <h2>Fila prioritária</h2>
                      <p>Ordenada por impacto Pareto</p>
                    </div>
                    <button
                      className="link-button"
                      onClick={() => navigate('queue')}
                    >
                      Ver todas <ArrowRight size={15} />
                    </button>
                  </div>
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>DEMANDA</th>
                          <th>PRIORIDADE</th>
                          <th>ESTADO</th>
                          <th>HOST</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {[...data.demands]
                          .sort((a, b) => pSort[a.priority] - pSort[b.priority])
                          .slice(0, 5)
                          .map(d => (
                            <tr
                              key={d.id}
                              onClick={() => {
                                setSelectedDemand(d.id);
                                navigate('queue');
                              }}
                              className="click-row"
                            >
                              <td>
                                <div className="cell-title">{d.title}</div>
                                <div className="cell-sub">
                                  {d.project} · {d.reference}
                                </div>
                              </td>
                              <td>
                                <Badge
                                  tone={
                                    d.priority === 'P0'
                                      ? 'prio0'
                                      : d.priority === 'P1'
                                        ? 'prio1'
                                        : 'neutral'
                                  }
                                >
                                  {d.priority}
                                </Badge>
                              </td>
                              <td>
                                <Tone state={d.state} />
                              </td>
                              <td>
                                <span className="host-micro">
                                  {data.hosts.find(h => h.id === d.host)
                                    ?.name || 'A definir'}
                                </span>
                              </td>
                              <td>
                                <ChevronRight size={16} />
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </section>
                <section className="panel next-action">
                  <div className="panel-head">
                    <div>
                      <h2>Próximo passo seguro</h2>
                      <p>Ação permitida · sem mutação</p>
                    </div>
                    <span className="tiny-icon">
                      <Zap size={17} />
                    </span>
                  </div>
                  <div className="action-highlight">
                    <div className="action-kicker">
                      <span className="step-number">01</span> PARETO /
                      PRIORIDADE P0
                    </div>
                    <h3>Revalidar a prontidão do Desktop PC24x7</h3>
                    <p>
                      Conferir runner, perfil NORMAL, SHA, sessão, Gateway,
                      worktree, lease e custo por fonte autorizada, sem
                      despachar tarefas.
                    </p>
                    <div className="mini-divider" />
                    <div className="action-meta">
                      <span>
                        <Monitor size={15} /> DESKTOP-PDQK954
                      </span>
                      <span>
                        <ShieldCheck size={15} /> Risk 1
                      </span>
                    </div>
                  </div>
                  <div className="action-warning">
                    <AlertCircle size={16} /> Ainda não há host com{' '}
                    <code>ready_for_work=true</code> comprovado.
                  </div>
                  <button
                    className="btn btn-primary btn-full"
                    onClick={() => openRecheck('desktop')}
                  >
                    Preparar registro de evidência <ArrowRight size={16} />
                  </button>
                </section>
              </div>
              <div className="overview-grid bottom-grid">
                <section className="panel">
                  <div className="panel-head">
                    <div>
                      <h2>Mapa de hosts</h2>
                      <p>Elegibilidade conservadora</p>
                    </div>
                    <button
                      className="link-button"
                      onClick={() => navigate('hosts')}
                    >
                      Comparar <ArrowRight size={15} />
                    </button>
                  </div>
                  <div className="host-compact-grid">
                    {data.hosts.map(h => (
                      <button
                        className="host-compact"
                        key={h.id}
                        onClick={() => {
                          setHostSelection(h.id);
                          navigate('hosts');
                        }}
                      >
                        <span className="host-compact-top">
                          <span className="device-icon">
                            {h.id === 'noteri' ? (
                              <Laptop2 size={18} />
                            ) : (
                              <Monitor size={18} />
                            )}
                          </span>
                          <Badge tone="danger">Não apto</Badge>
                        </span>
                        <strong>{h.name}</strong>
                        <small>{h.role}</small>
                        <div className="compact-bottom">
                          <span>{CAT[h.category]}</span>
                          <ChevronRight size={15} />
                        </div>
                      </button>
                    ))}
                  </div>
                </section>
                <section className="panel evidence-panel">
                  <div className="panel-head">
                    <div>
                      <h2>Cadeia de evidências</h2>
                      <p>Do registro até a certificação</p>
                    </div>
                    <FileCheck2 size={19} className="muted" />
                  </div>
                  <div className="evidence-steps">
                    <div className="evidence-step">
                      <span className="step-ring dark">1</span>
                      <div>
                        <strong>Referência identificada</strong>
                        <small>Issue, run, commit ou fonte oficial</small>
                      </div>
                    </div>
                    <div className="evidence-step">
                      <span className="step-ring">2</span>
                      <div>
                        <strong>SHA e ambiente vinculados</strong>
                        <small>Registro consistente e recente</small>
                      </div>
                    </div>
                    <div className="evidence-step">
                      <span className="step-ring">3</span>
                      <div>
                        <strong>Readback independente</strong>
                        <small>Confirmação fora da declaração manual</small>
                      </div>
                    </div>
                    <div className="evidence-step">
                      <span className="step-ring">4</span>
                      <div>
                        <strong>Execução governada</strong>
                        <small>Indisponível neste site</small>
                      </div>
                    </div>
                  </div>
                </section>
              </div>
            </>
          )}
          {page === 'queue' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">BACKLOG GOVERNADO</div>
                  <h1>Fila de demandas</h1>
                  <p>
                    Demandas priorizadas com bloqueios, dependências, evidências
                    e próxima ação.
                  </p>
                </div>
                <button
                  className="btn btn-primary"
                  onClick={() => openDemand()}
                >
                  <Plus size={16} /> Adicionar demanda
                </button>
              </div>
              <div className="queue-layout">
                <section className="panel queue-main">
                  <div className="filters">
                    <label className="search-field">
                      <Search size={17} />
                      <input
                        aria-label="Buscar demandas"
                        placeholder="Buscar demanda, repositório ou issue..."
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                      />
                    </label>
                    <label className="select-filter">
                      <Filter size={15} />
                      <select
                        aria-label="Filtrar prioridade"
                        value={priority}
                        onChange={e => setPriority(e.target.value)}
                      >
                        <option>Todas</option>
                        <option>P0</option>
                        <option>P1</option>
                        <option>P2</option>
                      </select>
                    </label>
                    <label className="select-filter">
                      <select
                        aria-label="Filtrar estado"
                        value={stateFilter}
                        onChange={e => setStateFilter(e.target.value)}
                      >
                        <option>Todos</option>
                        {Object.keys(STATE).map(s => (
                          <option key={s} value={s}>
                            {STATE[s as DemandState]}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="list-count">
                    {sorted.length} demanda(s) · classificação Pareto
                  </div>
                  <div className="demand-list">
                    {sorted.length === 0 ? (
                      <div className="empty-state">
                        <Search size={27} />
                        <strong>Nenhuma demanda encontrada</strong>
                        <span>Altere os filtros ou cadastre uma demanda.</span>
                      </div>
                    ) : (
                      sorted.map(d => (
                        <button
                          key={d.id}
                          className={
                            'demand-row ' +
                            (selected?.id === d.id ? 'selected' : '')
                          }
                          onClick={() => setSelectedDemand(d.id)}
                        >
                          <div className="demand-row-top">
                            <Badge
                              tone={
                                d.priority === 'P0'
                                  ? 'prio0'
                                  : d.priority === 'P1'
                                    ? 'prio1'
                                    : 'neutral'
                              }
                            >
                              {d.priority}
                            </Badge>
                            <Tone state={d.state} />
                            <ChevronRight size={17} />
                          </div>
                          <strong>{d.title}</strong>
                          <div className="demand-row-sub">
                            {d.project} <span>·</span> {d.reference}
                          </div>
                          <div className="demand-row-foot">
                            <span>
                              <Server size={14} />
                              {data.hosts.find(h => h.id === d.host)?.name ||
                                'Sem host'}
                            </span>
                            <span>
                              <AlertCircle size={14} />
                              {CAT[d.category]}
                            </span>
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                </section>
                <section className="panel demand-detail">
                  {selected ? (
                    <>
                      <div className="detail-head">
                        <div>
                          <div className="eyebrow">
                            DETALHE DA DEMANDA · {selected.id}
                          </div>
                          <h2>{selected.title}</h2>
                        </div>
                        <button
                          className="icon-btn"
                          title="Editar demanda"
                          onClick={() => openDemand(selected)}
                        >
                          <Settings2 size={18} />
                        </button>
                      </div>
                      <div className="detail-badges">
                        <Badge
                          tone={selected.priority === 'P0' ? 'prio0' : 'prio1'}
                        >
                          {selected.priority} Pareto
                        </Badge>
                        <Tone state={selected.state} />
                        <Badge tone="danger">{CAT[selected.category]}</Badge>
                      </div>
                      <div className="detail-section">
                        <h3>Rastreabilidade</h3>
                        <div className="keyvalues">
                          <div>
                            <span>Repositório</span>
                            <strong>{selected.repo}</strong>
                          </div>
                          <div>
                            <span>Issue / PR</span>
                            <strong>
                              {selected.url ? (
                                <a
                                  href={safeUrl(selected.url) || undefined}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  {selected.reference || 'Abrir referência'}{' '}
                                  <ExternalLink size={13} />
                                </a>
                              ) : (
                                selected.reference || 'Não informada'
                              )}
                            </strong>
                          </div>
                          <div>
                            <span>SHA admitido</span>
                            <strong className="mono">
                              {shortSha(selected.sha)}
                            </strong>
                          </div>
                          <div>
                            <span>Tipo de execução</span>
                            <strong>{selected.kind}</strong>
                          </div>
                          <div>
                            <span>Host preferencial</span>
                            <strong>
                              {data.hosts.find(h => h.id === selected.host)
                                ?.name || 'A definir'}
                            </strong>
                          </div>
                          <div>
                            <span>Custo previsto</span>
                            <strong className="risk-value">
                              {selected.cost}
                            </strong>
                          </div>
                          <div>
                            <span>Responsável</span>
                            <strong>{selected.owner || 'Não designado'}</strong>
                          </div>
                        </div>
                      </div>
                      <div className="detail-section">
                        <h3>Dependências</h3>
                        <p>{selected.dependencies || 'Não informadas'}</p>
                      </div>
                      <div className="detail-section">
                        <h3>Evidências exigidas</h3>
                        <p>{selected.required || 'Não informadas'}</p>
                      </div>
                      <div className="detail-section next-sec">
                        <h3>Próxima ação segura</h3>
                        <p>{selected.next}</p>
                        <div className="detail-footnote">
                          <LockKeyhole size={15} /> Não executa comandos em
                          hosts nem dispatch.
                        </div>
                      </div>
                      <div className="detail-section">
                        <h3>
                          Registros de evidência{' '}
                          <span className="count-chip">
                            {
                              data.evidences.filter(
                                x => x.demand === selected.id
                              ).length
                            }
                          </span>
                        </h3>
                        {data.evidences.filter(x => x.demand === selected.id)
                          .length ? (
                          <div className="evidence-list">
                            {data.evidences
                              .filter(x => x.demand === selected.id)
                              .map(item => (
                                <div className="evidence-record" key={item.id}>
                                  <FileText size={16} />
                                  <div>
                                    <strong>{item.title}</strong>
                                    <small>
                                      {fmt(item.when)} · {item.type} · não
                                      homologada
                                    </small>
                                    <a
                                      href={safeUrl(item.url) || undefined}
                                      target="_blank"
                                      rel="noreferrer"
                                    >
                                      Abrir fonte <ExternalLink size={12} />
                                    </a>
                                  </div>
                                </div>
                              ))}
                          </div>
                        ) : (
                          <div className="empty-evidence">
                            Nenhuma evidência manual anexada.
                          </div>
                        )}
                        <button
                          className="btn btn-secondary btn-full"
                          onClick={() => openEvidence(selected.id)}
                        >
                          <Plus size={15} /> Registrar evidência
                        </button>
                      </div>
                      <div className="detail-source">
                        <Info size={14} />
                        {selected.source}{' '}
                        {selected.human ? '· intervenção humana indicada' : ''}
                      </div>
                    </>
                  ) : (
                    <div className="empty-state">Selecione uma demanda</div>
                  )}
                </section>
              </div>
            </>
          )}
          {page === 'hosts' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">RUNTIME PLATFORM</div>
                  <h1>Prontidão dos hosts</h1>
                  <p>
                    Comparação entre computadores físicos. Dados declarados
                    nunca liberam execução automaticamente.
                  </p>
                </div>
                <button
                  className="btn btn-primary"
                  onClick={() => openRecheck(hostSelection)}
                >
                  <RefreshCcw size={16} /> Nova revalidação
                </button>
              </div>
              <div className="banner banner-notice">
                <AlertCircle size={18} />
                <div>
                  <strong>
                    0 de {data.hosts.length} hosts aptos para trabalho
                  </strong>
                  <span>
                    ready_for_work é sempre false sem recibo independente de
                    admissão, custo e estado atual do host.
                  </span>
                </div>
              </div>
              <div className="hosts-grid">
                {data.hosts.map(h => (
                  <button
                    key={h.id}
                    className={
                      'host-tile ' + (hostSelection === h.id ? 'selected' : '')
                    }
                    onClick={() => setHostSelection(h.id)}
                  >
                    <div className="host-tile-top">
                      <div className="device-icon large">
                        {h.id === 'noteri' ? (
                          <Laptop2 size={22} />
                        ) : (
                          <Monitor size={22} />
                        )}
                      </div>
                      <Badge tone="danger">Bloqueado</Badge>
                    </div>
                    <h3>{h.name}</h3>
                    <p>{h.model}</p>
                    <div className="tile-progress">
                      <div>
                        <span>Verificações declaradas</span>
                        <strong>
                          {gatesCount(h)}/{GATES.length}
                        </strong>
                      </div>                      <div className="progress-track">
                        <span
                          style={{
                            width:
                              String((gatesCount(h) / GATES.length) * 100) +
                              '%',
                          }}
                        />
                      </div>
                    </div>
                    <div className="tile-footer">
                      <span>
                        <Clock3 size={13} />
                        {h.lastCheck ? fmt(h.lastCheck) : 'Sem leitura atual'}
                      </span>
                      <ChevronRight size={16} />
                    </div>
                  </button>
                ))}
              </div>
              <div className="overview-grid host-detail-grid">
                <section className="panel">
                  <div className="panel-head">
                    <div>
                      <h2>{selectedHost.name}</h2>
                      <p>
                        {selectedHost.role} · {selectedHost.source}
                      </p>
                    </div>
                    <Badge tone="danger">ready_for_work = false</Badge>
                  </div>
                  <div className="host-fields">
                    <div>
                      <span>Identidade física</span>
                      <strong>{selectedHost.model}</strong>
                    </div>
                    <div>
                      <span>Versão observada</span>
                      <strong>{selectedHost.version}</strong>
                    </div>
                    <div>
                      <span>Labels</span>
                      <strong>{selectedHost.labels.join(', ')}</strong>
                    </div>
                    <div>
                      <span>SHA admitido</span>
                      <strong className="mono">
                        {shortSha(selectedHost.sha)}
                      </strong>
                    </div>
                  </div>
                  <div className="gates-grid">
                    {GATES.map(([key, label]) => (
                      <div key={key} className="gate-item">
                        <span
                          className={'gate-icon ' + selectedHost.gates[key]}
                        >
                          {selectedHost.gates[key] === 'declarado' ? (
                            <Check size={15} />
                          ) : selectedHost.gates[key] === 'falhou' ? (
                            <X size={15} />
                          ) : (
                            <CircleHelp size={15} />
                          )}
                        </span>
                        <span>{label}</span>
                        <small>
                          {selectedHost.gates[key] === 'declarado'
                            ? 'Declarado'
                            : selectedHost.gates[key] === 'falhou'
                              ? 'Falhou'
                              : 'Sem prova'}
                        </small>
                      </div>
                    ))}
                  </div>
                  <div className="blocker-box">
                    <strong>
                      <ShieldAlert size={16} /> Bloqueio:{' '}
                      {CAT[selectedHost.category]}
                    </strong>
                    <p>{selectedHost.blocker}</p>
                    <small>
                      {selectedHost.human
                        ? 'Pode exigir ação humana governada'
                        : 'Próximo passo: leitura e reconciliação sem mutação'}
                    </small>
                  </div>
                  <div className="panel-actions">
                    <button
                      className="btn btn-primary"
                      onClick={() => openRecheck(selectedHost.id)}
                    >
                      <Plus size={16} /> Registrar revalidação
                    </button>
                    <button
                      className="btn btn-secondary"
                      onClick={() => navigate('history')}
                    >
                      Histórico <ArrowRight size={15} />
                    </button>
                  </div>
                </section>
                <section className="panel comparison-panel">
                  <div className="panel-head">
                    <div>
                      <h2>Comparação direta</h2>
                      <p>
                        Somente declarações — não substituem a autoridade do
                        host
                      </p>
                    </div>
                    <SlidersHorizontal size={18} className="muted" />
                  </div>
                  <div className="table-scroll">
                    <table className="compare-table">
                      <thead>
                        <tr>
                          <th>REQUISITO</th>
                          {data.hosts.map(h => (
                            <th key={h.id} title={h.name}>
                              {h.id === 'desktop'
                                ? 'PC24x7'
                                : h.id === 'lenovo'
                                  ? 'Lenovo'
                                  : h.id === 'noteri'
                                    ? 'Noteri'
                                    : 'OptiPlex'}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {GATES.map(([key, label]) => (
                          <tr key={key}>
                            <td>{label}</td>
                            {data.hosts.map(h => (
                              <td key={h.id}>
                                <span
                                  title={
                                    h.gates[key] === 'declarado'
                                      ? 'Declarado sem homologação'
                                      : h.gates[key] === 'falhou'
                                        ? 'Falha informada'
                                        : 'Não verificado'
                                  }
                                  className={'status-cell ' + h.gates[key]}
                                >
                                  {h.gates[key] === 'declarado' ? (
                                    <Check size={16} />
                                  ) : h.gates[key] === 'falhou' ? (
                                    <X size={16} />
                                  ) : (
                                    <MoreHorizontal size={17} />
                                  )}
                                </span>
                              </td>
                            ))}
                          </tr>
                        ))}
                        <tr className="final-row">
                          <td>ready_for_work</td>
                          {data.hosts.map(h => (
                            <td key={h.id}>
                              <Badge tone="danger">FALSE</Badge>
                            </td>
                          ))}
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div className="compare-legend">
                    <span>
                      <span className="legend-symbol">···</span>Sem prova
                    </span>
                    <span>
                      <Check size={14} />
                      Declarado
                    </span>
                    <span>
                      <X size={14} />
                      Falhou
                    </span>
                  </div>
                </section>
              </div>
            </>
          )}
          {page === 'history' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">AUDITORIA DE REGISTROS</div>
                  <h1>Histórico de revalidações</h1>
                  <p>
                    Registro cronológico de sondas documentais. Nenhuma operação
                    remota é disparada.
                  </p>
                </div>
                <button
                  className="btn btn-primary"
                  onClick={() => openRecheck()}
                >
                  <Plus size={16} /> Registrar verificação
                </button>
              </div>
              <div className="panel history-panel">
                <div className="history-top">
                  <div>
                    <h2>Atividades registradas</h2>
                    <p>{data.history.length} registro(s) neste navegador</p>
                  </div>
                  <Badge tone="neutral">Sem telemetria integrada</Badge>
                </div>
                {data.history.length === 0 ? (
                  <div className="empty-state history-empty">
                    <FileClock size={34} />
                    <h3>Nenhuma revalidação registrada</h3>
                    <span>
                      Faça a primeira leitura por fonte governada e registre os
                      resultados, sem alterar os hosts.
                    </span>
                    <button
                      className="btn btn-primary"
                      onClick={() => openRecheck()}
                    >
                      Criar primeiro registro
                    </button>
                  </div>
                ) : (
                  <div className="timeline">
                    {data.history.map(r => (
                      <div key={r.id} className="timeline-row">
                        <span className="timeline-point" />
                        <div className="timeline-meta">
                          <strong>
                            {data.hosts.find(h => h.id === r.host)?.name ||
                              r.host}
                          </strong>
                          <span>
                            {fmt(r.when)} · {r.id}
                          </span>
                        </div>
                        <div className="timeline-content">
                          <div className="timeline-tags">
                            <Badge tone="danger">Não homologado</Badge>
                            <Badge>{CAT[r.category]}</Badge>
                            {r.human && (
                              <Badge tone="warning">Ação humana</Badge>
                            )}
                          </div>
                          <p>{r.note}</p>
                          <small>
                            SHA: <span className="mono">{shortSha(r.sha)}</span>{' '}
                            · Fonte: {r.source}
                          </small>
                          <div className="record-gates">
                            {
                              GATES.filter(([k]) => r.gates[k] === 'declarado')
                                .length
                            }
                            /{GATES.length} requisitos declarados · sem
                            liberação de worker
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
          {page === 'e2e' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">CERTIFICAÇÃO DE CONTINUIDADE</div>
                  <h1>Fluxo guiado E2E</h1>
                  <p>
                    Separar pickup individual de recuperação real da mesma
                    tarefa em outro computador.
                  </p>
                </div>
                <Badge tone="danger">E2E não comprovado</Badge>
              </div>
              <div className="banner banner-danger">
                <ShieldAlert size={20} />
                <div>
                  <strong>Pickup isolado não é failover.</strong>
                  <span>
                    São necessários dois hosts físicos distintos, mesmo
                    request_id e SHA, checkpoint durável, posse exclusiva,
                    replay, testes negativos e leitura independente.
                  </span>
                </div>
              </div>
              <div className="flow-layout">
                <section className="panel flow-main">
                  <div className="panel-head">
                    <div>
                      <h2>Checklist de qualificação</h2>
                      <p>Preencha campos documentais. Não inicia execução.</p>
                    </div>
                    <span className="flow-progress">
                      {flowInputs.filter(Boolean).length}/10
                    </span>
                  </div>
                  <div className="flow-stages">
                    <div className="flow-stage">
                      <div className="flow-stage-head">
                        <span className="step-ring dark">1</span>
                        <div>
                          <h3>Origem e host inicial</h3>
                          <p>
                            Identidade física, mesma tarefa e código admitido
                          </p>
                        </div>
                      </div>
                      <div className="form-grid">
                        <label>
                          Host A
                          <select
                            value={flow.first}
                            onChange={e => setFlow('first', e.target.value)}
                          >
                            <option value="">Selecione</option>
                            {data.hosts.map(h => (
                              <option key={h.id} value={h.id}>
                                {h.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Host B (físico distinto)
                          <select
                            value={flow.second}
                            onChange={e => setFlow('second', e.target.value)}
                          >
                            <option value="">Selecione</option>
                            {data.hosts.map(h => (
                              <option key={h.id} value={h.id}>
                                {h.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Request ID único
                          <input
                            placeholder="ID da mesma tarefa"
                            value={flow.request}
                            onChange={e => setFlow('request', e.target.value)}
                          />
                        </label>
                        <label>
                          SHA completo (40 hex)
                          <input
                            placeholder="SHA da origem versionada"
                            value={flow.sha}
                            onChange={e => setFlow('sha', e.target.value)}
                          />
                        </label>
                      </div>
                      {flow.first &&
                        flow.second &&
                        flow.first === flow.second && (
                          <div className="inline-error">
                            <Ban size={14} /> Host A e Host B não podem ser a
                            mesma máquina.
                          </div>
                        )}
                    </div>
                    <div className="flow-stage">
                      <div className="flow-stage-head">
                        <span className="step-ring">2</span>
                        <div>
                          <h3>Checkpoint e exclusividade</h3>
                          <p>
                            Provar estado durável, CAS e liberação da posse
                            anterior
                          </p>
                        </div>
                      </div>
                      <label>
                        SHA-256 do checkpoint durável (64 hex)
                        <input
                          placeholder="Hash do mesmo checkpoint relido"
                          value={flow.checkpoint}
                          onChange={e => setFlow('checkpoint', e.target.value)}
                        />
                      </label>
                      <label className="checkline">
                        <input
                          type="checkbox"
                          checked={flow.lease}
                          onChange={e => setFlow('lease', e.target.checked)}
                        />
                        <span>
                          Existe evidência de lease exclusivo e liberação do
                          Host A
                        </span>
                      </label>
                    </div>
                    <div className="flow-stage">
                      <div className="flow-stage-head">
                        <span className="step-ring">3</span>
                        <div>
                          <h3>Retomada e validação</h3>
                          <p>
                            Mesmo request_id assumido pelo Host B com resultado
                            verificável
                          </p>
                        </div>
                      </div>
                      <label className="checkline">
                        <input
                          type="checkbox"
                          checked={flow.replay}
                          onChange={e => setFlow('replay', e.target.checked)}
                        />
                        <span>
                          Replay idempotente da mesma tarefa documentado
                        </span>
                      </label>
                      <label>
                        URL HTTPS do Validator independente
                        <input
                          placeholder="https://github.com/.../actions/runs/..."
                          value={flow.validator}
                          onChange={e => setFlow('validator', e.target.value)}
                        />
                      </label>
                      <label>
                        URL HTTPS do readback independente
                        <input
                          placeholder="https://github.com/.../issues/..."
                          value={flow.readback}
                          onChange={e => setFlow('readback', e.target.value)}
                        />
                      </label>
                      <label className="checkline">
                        <input
                          type="checkbox"
                          checked={flow.negative}
                          onChange={e => setFlow('negative', e.target.checked)}
                        />
                        <span>
                          Casos negativos (SHA inválido, lease duplicado e host
                          inelegível) documentados
                        </span>
                      </label>
                    </div>
                  </div>
                </section>
                <aside className="panel flow-side">
                  <h2>Decisão do gate</h2>
                  <div className="decision-circle">
                    <ShieldAlert size={30} />
                  </div>
                  <h3>
                    {flowValid
                      ? 'Documentação preenchida'
                      : 'Bloqueado para execução'}
                  </h3>
                  <p>
                    {flowValid
                      ? 'Os campos locais estão completos, mas ainda exigem confirmação por fonte independente e runtime governado.'
                      : 'Faltam requisitos documentais. Nenhum preenchimento manual torna o E2E comprovado.'}
                  </p>
                  <div className="decision-rule">
                    <span>Pickup individual</span>
                    <Badge tone="warning">Prova parcial</Badge>
                  </div>
                  <div className="decision-rule">
                    <span>Continuidade física</span>
                    <Badge tone="danger">Não comprovada</Badge>
                  </div>
                  <div className="decision-rule">
                    <span>Executor liberado</span>
                    <Badge tone="danger">NÃO</Badge>
                  </div>
                  <div className="mini-divider" />
                  <h4>Próxima ação</h4>
                  <p>
                    {flowValid
                      ? 'Submeter o conjunto de evidências ao validador independente pelo canal autorizado.'
                      : 'Revalidar dois hosts e preencher os requisitos com recibos externos verificáveis.'}
                  </p>
                  <button
                    className="btn btn-secondary btn-full"
                    onClick={() => navigate('hosts')}
                  >
                    Ver prontidão dos hosts <ArrowRight size={15} />
                  </button>
                  <div className="flow-side-note">
                    <LockKeyhole size={15} /> Não há botão de dispatch, reboot,
                    merge, instalação nem alteração administrativa.
                  </div>
                </aside>
              </div>
            </>
          )}
          {page === 'sources' && <PublicGithubReadOnly />}
          {page === 'rules' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">CONTROLES OPERACIONAIS</div>
                  <h1>Governança e segurança</h1>
                  <p>
                    O painel prepara decisões, registra a trilha e impede
                    alegações sem prova externa.
                  </p>
                </div>
                <Badge tone="good">Modo de planejamento</Badge>
              </div>
              <div className="rules-grid">
                <section className="panel policy-hero">
                  <div className="policy-icon">
                    <ShieldCheck size={29} />
                  </div>
                  <h2>Fail-closed por padrão</h2>
                  <p>
                    Uma declaração manual não altera o estado efetivo de uma
                    máquina nem autoriza o primeiro comando remoto. No caso de
                    qualquer incerteza, o estado permanece bloqueado.
                  </p>
                  <div className="policy-chips">
                    <Badge tone="good">Read-only</Badge>
                    <Badge tone="good">Sem dispatch</Badge>
                    <Badge tone="good">Sem Docker</Badge>
                    <Badge tone="good">Sem GUI</Badge>
                  </div>
                </section>
                <section className="panel">
                  <h2>Operações que este site não oferece</h2>
                  <div className="prohibited-grid">
                    {[
                      'Dispatch ou ativação de worker',
                      'Reboot ou shutdown',
                      'Merge, push ou deploy do ReqSys',
                      'Instalação ou privilégio administrativo',
                      'Credenciais, tokens e segredos',
                      'Docker, GUI remota ou terminal direto',
                    ].map(x => (
                      <div key={x}>
                        <Ban size={16} />
                        {x}
                      </div>
                    ))}
                  </div>
                </section>
                <section className="panel">
                  <h2>Condições obrigatórias de elegibilidade</h2>
                  <div className="policy-list">
                    {[
                      'Identidade física e labels com leitura independente',
                      'Perfil NORMAL e SHA exato admitido',
                      'SESSION_LAUNCH_OK e state_validated=true',
                      'Gateway, worktree e lease exclusivos',
                      'Dependências nativas e runner comprovados',
                      'Custo incremental R$ 0,00 com evidência de franquia/hard stop',
                      'E2E físico, Validator independente e replay quando aplicáveis',
                    ].map((x, i) => (
                      <div key={x}>
                        <span className="number-chip">{i + 1}</span>
                        {x}
                      </div>
                    ))}
                  </div>
                </section>
                <section className="panel">
                  <h2>Fonte de verdade e armazenamento</h2>
                  <div className="policy-list">
                    <div>
                      <Database size={17} />
                      Dados editados ficam apenas neste navegador
                      (localStorage).
                    </div>
                    <div>
                      <CloudOff size={17} />
                      Não há sincronização automática com GitHub, runners, TODO
                      Global ou outros PCs.
                    </div>
                    <div>
                      <FileCheck2 size={17} />
                      Registros são declarações não homologadas, mesmo com URL
                      informada.
                    </div>
                    <div>
                      <LockKeyhole size={17} />
                      Não registre segredos nem dados pessoais sensíveis.
                    </div>
                  </div>
                  <div className="policy-export">
                    <button className="btn btn-secondary" onClick={exportData}>
                      <Download size={15} /> Exportar backup
                    </button>
                    <button
                      className="btn btn-secondary"
                      onClick={() => setModal('import')}
                    >
                      <Upload size={15} /> Importar registros
                    </button>
                  </div>
                </section>
              </div>
              <div className="policy-footer">
                <strong>Fonte normativa:</strong>{' '}
                <a
                  href="https://github.com/ericson-j-santos/chatgpt-operational-rules/tree/86abe65b22781c2f608a7d7286ce3a28cd48aaaf"
                  target="_blank"
                  rel="noreferrer"
                >
                  chatgpt-operational-rules · v1.6.20 · SHA 86abe65b…{' '}
                  <ExternalLink size={13} />
                </a>
                <span>
                  Leitura de referência em 08/11/2026; confirmar novamente antes
                  de executar.
                </span>
              </div>
            </>
          )}
          <footer className="footer">
            <span>ReqSys Control · Painel local de coordenação</span>
            <span>
              <span className="micro-dot red" />
              Sem conexão operacional · R$ 0,00 adicional · Não é sistema de
              autorização
            </span>
          </footer>
        </div>
      </main>
      {modal && (
        <div
          className="modal-backdrop"
          onMouseDown={e => {
            if (e.target === e.currentTarget) setModal(null);
          }}
        >
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Formulário operacional"
          >
            <header className="modal-header">
              <div>
                <div className="eyebrow">REGISTRO LOCAL · SEM DISPATCH</div>
                <h2>
                  {modal === 'demand'
                    ? draft.id
                      ? 'Editar demanda'
                      : 'Nova demanda'
                    : modal === 'recheck'
                      ? 'Registrar revalidação'
                      : modal === 'evidence'
                        ? 'Registrar evidência'
                        : 'Importar registros'}
                </h2>
              </div>
              <button
                className="icon-btn"
                aria-label="Fechar formulário"
                onClick={() => setModal(null)}
              >
                <X size={20} />
              </button>
            </header>
            {modal === 'demand' && (
              <form className="modal-body" onSubmit={saveDemand}>
                <div className="form-grid">
                  <label className="full">
                    Título da demanda *
                    <input
                      required
                      maxLength={200}
                      value={draft.title}
                      onChange={e =>
                        setDraft(v => ({ ...v, title: e.target.value }))
                      }
                      placeholder="Ex.: Validar E2E do ReqSys"
                    />
                  </label>
                  <label>
                    Projeto
                    <input
                      value={draft.project}
                      maxLength={100}
                      onChange={e =>
                        setDraft(v => ({ ...v, project: e.target.value }))
                      }
                    />
                  </label>
                  <label>
                    Repositório (owner/repo) *
                    <input
                      required
                      maxLength={160}
                      value={draft.repo}
                      onChange={e =>
                        setDraft(v => ({ ...v, repo: e.target.value }))
                      }
                      placeholder="ericson-j-santos/reqsys..."
                    />
                  </label>
                  <label>
                    Issue ou PR
                    <input
                      maxLength={100}
                      value={draft.reference}
                      onChange={e =>
                        setDraft(v => ({ ...v, reference: e.target.value }))
                      }
                      placeholder="Issue #123"
                    />
                  </label>
                  <label>
                    URL da referência (HTTPS)
                    <input
                      maxLength={500}
                      value={draft.url}
                      onChange={e =>
                        setDraft(v => ({ ...v, url: e.target.value }))
                      }
                      placeholder="https://github.com/..."
                    />
                  </label>
                  <label>
                    Prioridade
                    <select
                      value={draft.priority}
                      onChange={e =>
                        setDraft(v => ({
                          ...v,
                          priority: e.target.value as Priority,
                        }))
                      }
                    >
                      <option>P0</option>
                      <option>P1</option>
                      <option>P2</option>
                    </select>
                  </label>
                  <label>
                    Estado
                    <select
                      value={draft.state}
                      onChange={e =>
                        setDraft(v => ({
                          ...v,
                          state: e.target.value as DemandState,
                        }))
                      }
                    >
                      {Object.keys(STATE).map(s => (
                        <option value={s} key={s}>
                          {STATE[s as DemandState]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Tipo de execução
                    <input
                      maxLength={100}
                      value={draft.kind}
                      onChange={e =>
                        setDraft(v => ({ ...v, kind: e.target.value }))
                      }
                    />
                  </label>
                  <label>
                    Host preferencial
                    <select
                      value={draft.host}
                      onChange={e =>
                        setDraft(v => ({ ...v, host: e.target.value }))
                      }
                    >
                      {data.hosts.map(h => (
                        <option key={h.id} value={h.id}>
                          {h.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="full">
                    SHA admitido (40 hex; vazio = não admitido)
                    <input
                      maxLength={40}
                      value={draft.sha}
                      onChange={e =>
                        setDraft(v => ({ ...v, sha: e.target.value }))
                      }
                      placeholder="SHA completo validado externamente"
                    />
                  </label>
                  <label>                    Categoria do bloqueio
                    <select
                      value={draft.category}
                      onChange={e =>
                        setDraft(v => ({
                          ...v,
                          category: e.target.value as Category,
                        }))
                      }
                    >
                      {CATEGORIES.map(c => (
                        <option key={c} value={c}>
                          {CAT[c]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Custo previsto
                    <input
                      maxLength={100}
                      value={draft.cost}
                      onChange={e =>
                        setDraft(v => ({ ...v, cost: e.target.value }))
                      }
                    />
                  </label>
                  <label className="full">
                    Dependências
                    <textarea
                      rows={2}
                      maxLength={800}
                      value={draft.dependencies}
                      onChange={e =>
                        setDraft(v => ({ ...v, dependencies: e.target.value }))
                      }
                    />
                  </label>
                  <label className="full">
                    Evidências exigidas *
                    <textarea
                      required
                      rows={2}
                      maxLength={800}
                      value={draft.required}
                      onChange={e =>
                        setDraft(v => ({ ...v, required: e.target.value }))
                      }
                    />
                  </label>
                  <label className="full">
                    Próxima ação segura *
                    <textarea
                      required
                      rows={2}
                      maxLength={800}
                      value={draft.next}
                      onChange={e =>
                        setDraft(v => ({ ...v, next: e.target.value }))
                      }
                    />
                  </label>
                  <label>
                    Responsável
                    <input
                      maxLength={100}
                      value={draft.owner}
                      onChange={e =>
                        setDraft(v => ({ ...v, owner: e.target.value }))
                      }
                    />
                  </label>
                  <label className="checkline">
                    <input
                      type="checkbox"
                      checked={draft.human}
                      onChange={e =>
                        setDraft(v => ({ ...v, human: e.target.checked }))
                      }
                    />
                    <span>Dependência de ação humana</span>
                  </label>
                </div>
                <div className="modal-warning">
                  <LockKeyhole size={15} /> Mudar o estado da demanda não
                  autoriza executar ou marcar ready_for_work.
                </div>
                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setModal(null)}
                  >
                    Cancelar
                  </button>
                  <button className="btn btn-primary" type="submit">
                    Salvar demanda
                  </button>
                </div>
              </form>
            )}
            {modal === 'recheck' && (
              <form className="modal-body" onSubmit={saveRecheck}>
                <div className="form-grid">
                  <label>
                    Host
                    <select
                      value={rHost}
                      onChange={e => setRHost(e.target.value)}
                    >
                      {data.hosts.map(h => (
                        <option value={h.id} key={h.id}>
                          {h.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Categoria
                    <select
                      value={rCategory}
                      onChange={e => setRCategory(e.target.value as Category)}
                    >
                      {CATEGORIES.map(c => (
                        <option key={c} value={c}>
                          {CAT[c]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="full">
                    Fonte / run / recibo *
                    <input
                      required
                      maxLength={500}
                      value={rSource}
                      onChange={e => setRSource(e.target.value)}
                      placeholder="URL ou identificador de evidência governada"
                    />
                  </label>
                  <label className="full">
                    SHA da versão (40 hex; opcional)
                    <input
                      maxLength={40}
                      value={rSha}
                      onChange={e => setRSha(e.target.value)}
                    />
                  </label>
                </div>
                <div className="gate-form-title">
                  Resultados observados (autodeclarados)
                </div>
                <div className="recheck-gates">
                  {GATES.map(([key, label]) => (
                    <label key={key}>
                      <span>{label}</span>
                      <select
                        value={rGates[key]}
                        onChange={e =>
                          setRGates(v => ({
                            ...v,
                            [key]: e.target.value as GateState,
                          }))
                        }
                      >
                        <option value="nao_verificado">Não verificado</option>
                        <option value="declarado">Declarado como OK</option>
                        <option value="falhou">Falhou / ausente</option>
                      </select>
                    </label>
                  ))}
                </div>
                <div className="form-grid">
                  <label className="full">
                    Bloqueio / observação *
                    <textarea
                      required
                      rows={3}
                      value={rNote}
                      onChange={e => setRNote(e.target.value)}
                      placeholder="Registre a primeira falha determinante e a próxima leitura segura"
                    />
                  </label>
                  <label className="checkline full">
                    <input
                      type="checkbox"
                      checked={rHuman}
                      onChange={e => setRHuman(e.target.checked)}
                    />
                    <span>Exige ação humana (não executada)</span>
                  </label>
                </div>
                <div className="modal-warning">
                  <AlertCircle size={15} /> Este formulário não consulta o host.
                  Mesmo 11/11 declarações não geram autorização.
                </div>
                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setModal(null)}
                  >
                    Cancelar
                  </button>
                  <button className="btn btn-primary" type="submit">
                    Salvar revalidação
                  </button>
                </div>
              </form>
            )}
            {modal === 'evidence' && (
              <form className="modal-body" onSubmit={saveEvidence}>
                <div className="form-grid">
                  <label className="full">
                    Demanda
                    <select
                      value={ev.demand}
                      onChange={e =>
                        setEv(v => ({ ...v, demand: e.target.value }))
                      }
                    >
                      {data.demands.map(d => (
                        <option key={d.id} value={d.id}>
                          {d.id} · {d.title}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="full">
                    Descrição da evidência *
                    <input
                      required
                      maxLength={200}
                      value={ev.title}
                      onChange={e =>
                        setEv(v => ({ ...v, title: e.target.value }))
                      }
                    />
                  </label>
                  <label className="full">
                    URL HTTPS da fonte *
                    <input
                      required
                      maxLength={500}
                      value={ev.url}
                      onChange={e =>
                        setEv(v => ({ ...v, url: e.target.value }))
                      }
                      placeholder="https://github.com/..."
                    />
                  </label>
                  <label>
                    Tipo
                    <select
                      value={ev.type}
                      onChange={e =>
                        setEv(v => ({ ...v, type: e.target.value }))
                      }
                    >
                      <option>Observação manual</option>
                      <option>Recibo governado</option>
                      <option>Run de CI</option>
                      <option>Validator independente (a conferir)</option>
                      <option>Readback (a conferir)</option>
                    </select>
                  </label>
                  <label>
                    SHA vinculado (opcional)
                    <input
                      maxLength={40}
                      value={ev.sha}
                      onChange={e =>
                        setEv(v => ({ ...v, sha: e.target.value }))
                      }
                    />
                  </label>
                  <label className="full">
                    Responsável pela inclusão
                    <input
                      maxLength={100}
                      value={ev.author}
                      onChange={e =>
                        setEv(v => ({ ...v, author: e.target.value }))
                      }
                    />
                  </label>
                </div>
                <div className="modal-warning">
                  <Info size={15} /> O link é apenas catalogado; não há análise
                  automática do conteúdo nem homologação.
                </div>
                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setModal(null)}
                  >
                    Cancelar
                  </button>
                  <button type="submit" className="btn btn-primary">
                    Salvar evidência
                  </button>
                </div>
              </form>
            )}
            {modal === 'import' && (
              <form className="modal-body" onSubmit={importData}>
                <p className="form-explanation">
                  Importe um JSON exportado por este painel (até 1 MB).
                  Demandas, histórico e evidências são mesclados por ID.
                  Identidade e gates dos hosts não são importados nem
                  certificados.
                </p>
                <label>
                  Arquivo JSON
                  <input
                    type="file"
                    accept=".json,application/json"
                    onChange={e => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      if (file.size > 1024 * 1024) {
                        notify('Arquivo maior que 1 MB.');
                        return;
                      }
                      file
                        .text()
                        .then(setImportText)
                        .catch(() => notify('Falha na leitura do arquivo.'));
                    }}
                  />
                </label>
                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setModal(null)}
                  >
                    Cancelar
                  </button>
                  <button
                    className="btn btn-primary"
                    disabled={!importText}
                    type="submit"
                  >
                    Mesclar registros
                  </button>
                </div>
              </form>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
export default App;
