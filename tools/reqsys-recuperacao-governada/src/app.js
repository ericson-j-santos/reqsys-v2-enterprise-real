import './styles.css';

const SHA = '58dcd4200f412a866278027ba9e433439a03f3b3';
const KEY = 'reqsys-recovery-records-v1';
const tasks = [
  {
    id: 'a',
    priority: 'P0',
    title: 'Recuperar atualização permanente do Broker',
    repo: 'reqsys-v2-enterprise-real',
    issue: '#3096',
    host: 'DESKTOP-PDQK954',
    next: 'DESKTOP-RP23OGS',
    status: 'Bloqueio técnico',
    tone: 'red',
    sha: 'Não admitido',
    needs: 'Release íntegra, Gateway, backup isolado e autorização Risk2',
    proof:
      'SHA completo, manifesto, digest, teste negativo, rollback e readback físico',
    action: 'Preflight no canal existente; preparar stage-only sem ativação',
    owner: 'Runtime Platform Desktop',
    url: 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3096',
  },
  {
    id: 'b',
    priority: 'P0',
    title: 'Perfil nativo DEV sem Docker',
    repo: 'reqsys-v2-enterprise-real',
    issue: '#3138',
    host: 'DESKTOP-PDQK954',
    next: 'DESKTOP-RP23OGS',
    status: 'Falta de evidência',
    tone: 'amber',
    sha: 'Não admitido',
    needs: 'Manifesto nativo, novo label, CI, Gate Pre-PR, custo zero',
    proof: 'READY_FOR_PR, pickup físico no runner 22 e readback de SHA',
    action:
      'Desenhar capacidade nativa separada; não aplicar label Docker legado',
    owner: 'Runtime Platform / Engineering',
    url: 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3138',
  },
  {
    id: 'c',
    priority: 'P0',
    title: 'Retomada E2E entre hosts físicos',
    repo: 'e2e-platform',
    issue: '#10',
    host: 'DESKTOP-PDQK954',
    next: 'DESKTOP-RP23OGS',
    status: 'E2E bloqueado',
    tone: 'red',
    sha: 'Mesmo SHA a validar',
    needs: 'Dois hosts prontos, lease exclusiva, checkpoint CAS e Validator',
    proof:
      'Mesma tarefa/request_id, dois hosts físicos, replay sem duplicidade e readback',
    action:
      'Comparar readiness sem novo dispatch; certificar apenas após os gates',
    owner: 'E2E Platform / Runtime',
    url: 'https://github.com/ericson-j-santos/e2e-platform/issues/10',
  },
  {
    id: 'd',
    priority: 'P1',
    title: 'Gateway/journal e Worker Pool nativo Noteri',
    repo: 'noteri-runtime',
    issue: '#42',
    host: 'Noteri',
    next: 'DESKTOP-PDQK954',
    status: 'Técnico / ação humana',
    tone: 'amber',
    sha: 'Não admitido',
    needs: 'Journal íntegro, lock, referência de token protegida, serviço 8097',
    proof: 'Readback do journal, /health, /v1/contract, controle 401 e replay',
    action: 'Inventariar journal e serviço em modo somente leitura',
    owner: 'Runtime Platform Noteri',
    url: 'https://github.com/ericson-j-santos/noteri-runtime/issues/42',
  },
  {
    id: 'e',
    priority: 'P1',
    title: 'Reconciliar runner e identidade Lenovo',
    repo: 'desktop-pc24x7-runtime',
    issue: '#31',
    host: 'DESKTOP-RP23OGS',
    next: 'DESKTOP-PDQK954',
    status: 'Runner não verificado',
    tone: 'slate',
    sha: 'Recapturar',
    needs: 'Runner, labels, NORMAL, Launcher, Gateway, worktree e lease',
    proof: 'Recibo de runner atual + pickup com SHA atual',
    action: 'Consultar runner e capacidades por canal governado, sem dispatch',
    owner: 'Runtime Platform',
    url: 'https://github.com/ericson-j-santos/desktop-pc24x7-runtime/issues/31',
  },
];
const hosts = [
  {
    name: 'DESKTOP-PDQK954',
    identity: 'PC24x7 principal; identificação histórica',
    labels: 'pc24x7; perfil runtime legado exige Docker',
    normal: 'Pendente',
    session: 'Histórico; leitura atual pendente',
    gateway: 'Broker persistente incompleto',
    worktree: 'Não verificada',
    lease: 'Não verificada',
    runner: 'ID 22 online/Idle na issue de 10/11; estado atual desconhecido',
    block: 'Broker e manifesto nativo',
    command:
      'session_launcher.py --require-runner-version-preflight (somente pela sessão e Command Gateway governados)',
    source: tasks[0].url,
  },
  {
    name: 'Noteri',
    identity: 'Notebook autorizado; identidade física atual pendente',
    labels: 'DEV-base com pickup histórico; atuais a verificar',
    normal: 'Pendente',
    session: 'Pickup histórico; nova prova exigida',
    gateway: 'Journal/recovery-only pendente',
    worktree: 'Não verificada',
    lease: 'Não verificada',
    runner: 'Pickup histórico, não comprova runner online hoje',
    block: 'Journal, token protegido, Worker Pool 8097',
    command:
      'recover_noteri_gateway_journal.py apenas pela capability recovery-only, com hashes fixos e autorização Risk2',
    source: tasks[3].url,
  },
  {
    name: 'DESKTOP-RP23OGS',
    identity: 'Lenovo, identidade observada em pickup 28/10',
    labels: 'Labels atuais a reler',
    normal: 'Pendente',
    session: 'Preflight histórico; leitura atual pendente',
    gateway: 'Canário histórico; validar agora',
    worktree: 'Não verificada',
    lease: 'Não verificada',
    runner: 'ID 24 online/Idle em 28/10; hoje desconhecido',
    block: 'Sem prova de retomada mesma tarefa',
    command:
      'dual_host_preflight.py via sessão governada, somente leitura e sem dispatch',
    source: tasks[4].url,
  },
  {
    name: 'Dell OptiPlex 7080 Micro',
    identity: 'Inventário histórico: i9-10900T, 64 GB RAM',
    labels: 'Não comprovadas',
    normal: 'Pendente',
    session: 'Não comprovado',
    gateway: 'Não comprovado',
    worktree: 'Não verificada',
    lease: 'Não verificada',
    runner: 'Não comprovado',
    block: 'Onboarding, Gateway e runner sem evidência atual',
    command:
      'host_onboarding_report.py por capability aprovada; nenhuma instalação ou serviço automático',
    source:
      'https://github.com/ericson-j-santos/chatgpt-operational-rules/blob/main/docs/new-computer-onboarding.md',
  },
];
const steps = [
  [
    'Preflight somente leitura',
    'Identidade física, labels, NORMAL, SHA de regras, SESSION_LAUNCH_OK, Gateway, worktree e lease exclusivos.',
    'Falha bloqueia a rota; shell/GUI não são fallback.',
  ],
  [
    'Backup isolado',
    'Inventariar backup íntegro, digest e origem; preservar estado antigo.',
    'Backup sem readback bloqueia restauração.',
  ],
  [
    'Restauração controlada',
    'Preparar stage-only e rollback com SHA fixo e capability versionada.',
    'Ativação e alterações físicas exigem autorização separada.',
  ],
  [
    'Execução idempotente',
    'Registrar request_id, correlation_id, idempotency_key, host e efeito esperado.',
    'Nenhuma ação física é iniciada neste site.',
  ],
  [
    'Checkpoint durável',
    'CAS externo imutável com hash e recibo relido em canal independente.',
    'localStorage não prova durabilidade entre hosts.',
  ],
  [
    'Validação independente',
    'Validator separado, positivo, negativos e readback de estado.',
    'CI verde isolado não prova efeito físico.',
  ],
  [
    'Replay sem duplicação',
    'Repetir a mesma entrada somente por capability autorizada.',
    'Repetição não deve criar novo efeito.',
  ],
  [
    'Readback de SHA',
    'Confirmar SHA, digest e retomada da mesma tarefa em segundo host.',
    'Dois pickups independentes não comprovam failover.',
  ],
  [
    'Encerramento',
    'Comprovar gates aplicáveis, registrar responsável e sincronização do TODO Global.',
    'Sem recibo canônico, manter PARCIAL/BLOQUEADO.',
  ],
];
const esc = v =>
  String(v == null ? '' : v).replace(
    /[&<>"']/g,
    c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[
        c
      ]
  );
const http = v => {
  try {
    let u = new URL(v);
    return u.protocol === 'https:' ? u.href : '';
  } catch {
    return '';
  }
};
let records = [];
try {
  let x = JSON.parse(localStorage.getItem(KEY) || '[]');
  if (Array.isArray(x)) records = x.slice(-300);
} catch {}
let page = 'overview',
  chosen = 'a',
  filter = 'all',
  query = '',
  dialog = false,
  preset = {},
  message = '';
const nav = [
  ['overview', 'Visão geral', '◫'],
  ['queue', 'Fila Pareto', '≡'],
  ['hosts', 'Hosts autorizados', '▦'],
  ['flow', 'Fluxo guiado', '⇢'],
  ['records', 'Evidências e comandos', '▤'],
  ['logs', 'Logs e decisões', '◷'],
];
const root = document.getElementById('app');
function pill(text, tone) {
  return (
    '<span class="pill ' + (tone || 'slate') + '">' + esc(text) + '</span>'
  );
}
function ext(url, label) {
  return (
    '<a href="' +
    esc(http(url)) +
    '" target="_blank" rel="noopener noreferrer">' +
    esc(label) +
    ' ↗</a>'
  );
}
function head(k, t, desc) {
  return (
    '<div class="section-head"><div class="eyebrow">' +
    esc(k) +
    '</div><h2>' +
    esc(t) +
    '</h2><p>' +
    esc(desc) +
    '</p></div>'
  );
}
function overview() {
  return (
    '<div class="stats"><div><small>Pendências prioritárias</small><strong>5</strong><span>Issues em acompanhamento</span></div><div><small>Hosts comprovadamente prontos</small><strong>0 / 4</strong><span>Preflight atual pendente</span></div><div><small>Continuidade E2E</small><strong>Bloqueada</strong><span>Mesma tarefa, dois hosts: não comprovado</span></div><div><small>Custo incremental permitido</small><strong>R$ 0,00</strong><span>Fail-closed para custo desconhecido</span></div></div>' +
    '<div class="split"><div class="featured"><div class="eyebrow">PRÓXIMA INTERVENÇÃO PARETO</div><h2>Recuperar a atualização permanente do orquestrador.</h2><p>Corrigir a instalação incompleta do Desktop Admin Broker sem repetir canários e sem executar mudanças administrativas. Primeiro validar a capability existente, depois preparar stage-only e rollback.</p><div class="chips"><span>Alvo: DESKTOP-PDQK954</span><span>ReqSys #3096</span><span>Somente preparação</span></div><button class="btn light" data-page="flow">Abrir fluxo governado →</button></div>' +
    '<div class="panel"><h3>O que está comprovado?</h3><div class="fact"><b>Pickup individual</b><p>Há canários históricos no Desktop e no Lenovo.</p></div><div class="fact"><b>Recuperação permanente</b><p>Ainda não certificada no host físico.</p></div><div class="fact"><b>Continuidade entre hosts</b><p>A mesma tarefa não foi retomada com checkpoint comprovado.</p></div><div class="notice">Nenhum botão deste site chama GitHub Actions, Gateway, SSH ou serviços dos computadores.</div></div></div>' +
    '<div class="panel"><div class="between"><h3>Fila de desbloqueio</h3><button class="text-button" data-page="queue">Ver tudo →</button></div>' +
    tasks
      .slice(0, 4)
      .map(
        t =>
          '<button class="task-link" data-task="' +
          t.id +
          '"><b>' +
          t.priority +
          '</b><span><strong>' +
          esc(t.title) +
          '</strong><small>' +
          esc(t.repo) +
          ' · ' +
          t.issue +
          ' · ' +
          esc(t.host) +
          '</small></span>' +
          pill(t.status, t.tone) +
          '</button>'
      )
      .join('') +
    '</div>' +
    '<div class="panel info"><b>Fonte da verdade</b><p>GitHub e TODO Global são canônicos. O site é um registro LOCAL no navegador, com exportação JSON e hash. Não considera informação de 28/10 ou 10/11 como status ao vivo em 11/11.</p></div>'
  );
}
function queue() {
  const t = tasks.find(x => x.id === chosen) || tasks[0];
  const found = tasks.filter(
    t =>
      (filter === 'all' || filter === t.priority) &&
      (t.title + ' ' + t.repo + ' ' + t.issue + ' ' + t.host)
        .toLowerCase()
        .includes(query.toLowerCase())
  );
  return (
    head(
      'PARETO / RASTREABILIDADE',
      'Fila de pendências',
      'Nenhum SHA histórico é automaticamente admitido para execução.'
    ) +
    '<div class="panel"><div class="tools"><input id="q" aria-label="Pesquisar pendência" placeholder="Pesquisar issue ou host" value="' +
    esc(query) +
    '"><div class="filters">' +
    ['all', 'P0', 'P1']
      .map(
        f =>
          '<button data-filter="' +
          f +
          '" class="' +
          (filter === f ? 'on' : '') +
          '">' +
          (f === 'all' ? 'Todas' : f) +
          '</button>'
      )
      .join('') +
    '</div></div>' +
    '<div class="table-wrap"><table><thead><tr><th>Demanda</th><th>Host atual / retomada</th><th>SHA</th><th>Estado</th><th></th></tr></thead><tbody>' +
    found
      .map(
        x =>
          '<tr><td><b>' +
          x.priority +
          ' · ' +
          esc(x.title) +
          '</b><small>' +
          esc(x.repo) +
          ' / ' +
          x.issue +
          '</small></td><td>' +
          esc(x.host) +
          '<small>→ ' +
          esc(x.next) +
          '</small></td><td>' +
          esc(x.sha) +
          '</td><td>' +
          pill(x.status, x.tone) +
          '</td><td><button class="text-button" data-task="' +
          x.id +
          '">Ver →</button></td></tr>'
      )
      .join('') +
    '</tbody></table></div></div>' +
    '<div class="panel"><div class="between"><h3>' +
    esc(t.title) +
    '</h3>' +
    ext(t.url, 'Issue ' + t.issue) +
    '</div><div class="facts-grid"><div><small>Responsável</small><b>' +
    esc(t.owner) +
    '</b></div><div><small>Custo previsto</small><b>R$ 0,00 (provar)</b></div><div><small>Host atual</small><b>' +
    esc(t.host) +
    '</b></div><div><small>Retomada</small><b>' +
    esc(t.next) +
    '</b></div></div>' +
    '<div class="detail"><b>Dependências</b><p>' +
    esc(t.needs) +
    '</p><b>Evidência exigida</b><p>' +
    esc(t.proof) +
    '</p><b>Próxima ação segura</b><p>' +
    esc(t.action) +
    '</p></div><button class="btn primary" data-add="' +
    t.issue +
    '">Registrar evidência desta issue</button></div>'
  );
}
function hostLine(k, v) {
  return (
    '<div class="host-line"><span>' +
    esc(k) +
    '</span><b>' +
    esc(v) +
    '</b></div>'
  );
}
function hostsView() {
  return (
    head(
      'READINESS / INFRAESTRUTURA',
      'Hosts autorizados',
      'Sem acesso direto ao hardware. Desconhecido não significa offline.'
    ) +
    '<div class="hosts-grid">' +
    hosts
      .map(
        h =>
          '<div class="panel host-card"><div class="host-title"><div class="host-icon">▣</div><div><h3>' +
          esc(h.name) +
          '</h3><small>' +
          esc(h.identity) +
          '</small></div></div><div class="host-state">' +
          pill('ready_for_work = false', 'red') +
          ' Sem E2E atual</div>' +
          hostLine('Identidade física', h.identity) +
          hostLine('Labels', h.labels) +
          hostLine('Perfil NORMAL', h.normal) +
          hostLine('SESSION_LAUNCH_OK', h.session) +
          hostLine('Gateway', h.gateway) +
          hostLine('Worktree', h.worktree) +
          hostLine('Lease exclusiva', h.lease) +
          hostLine('Runner', h.runner) +
          '<div class="blocked"><b>Bloqueio ativo</b><p>' +
          esc(h.block) +
          '</p></div><p class="host-cmd"><b>Roteiro manual documental</b><span>' +
          esc(h.command) +
          '</span></p><div class="between"><button class="btn outline" data-host="' +
          esc(h.name) +
          '">Registrar comando</button>' +
          ext(h.source, 'Fonte') +
          '</div></div>'
      )
      .join('') +
    '</div>'
  );
}
function flow() {
  return (
    head(
      'CAPABILITY / GATES',
      'Fluxo guiado de recuperação',
      'Etapas documentais. Registrar uma evidência não promove a etapa para aprovada.'
    ) +
    '<div class="panel info"><b>Requisito estrutural</b><p>Capability versionada fixa, SHA admitido, sessão exclusiva, Gateway, backup/reversão, execução idempotente, checkpoint externo, readback independente e mesma tarefa retomada em outro host físico.</p></div>' +
    '<div class="step-layout"><div class="step-list">' +
    steps
      .map(
        (s, i) =>
          '<button class="step" data-step="' +
          i +
          '"><span class="num">' +
          String(i + 1).padStart(2, '0') +
          '</span><span><strong>' +
          esc(s[0]) +
          '</strong><small>' +
          records.filter(r => r.phase === i).length +
          ' registro(s) locais; gate não validado</small></span><span>›</span></button>'
      )
      .join('') +
    '</div><div class="panel"><h3>Critérios de bloqueio</h3><ul class="checks"><li>Perfil NORMAL, regras e sessão comprovados.</li><li>Backup íntegro antes da restauração.</li><li>Somente capability allowlisted e operação autorizada.</li><li>Sem Docker, GUI ou terminal genérico.</li><li>CAS durável fora do executor.</li><li>Validator e controles negativos reais.</li><li>Mesmo request_id em dois hosts físicos distintos.</li><li>TODO Global persistido com readback.</li></ul><div class="notice">Estado: BLOQUEADO até evidência real. Nenhum dispatch, reboot ou merge automático.</div></div></div>' +
    '<div class="panel"><h3>Pickup individual ≠ continuidade E2E</h3><div class="compare"><div><b>Pickup individual</b><p>Um runner recebeu um job em um SHA específico. É progresso local, não failover.</p></div><div><b>Continuidade E2E</b><p>O segundo host físico assume a mesma tarefa após checkpoint, lease liberada e leitura independente, sem duplicação.</p></div></div></div>'
  );
}
function item(r) {
  return (
    '<div class="entry"><div><strong>' +
    esc(r.title) +
    '</strong><small>' +
    esc(r.kind) +
    ' · ' +
    esc(r.host || 'Geral') +
    ' · ' +
    esc(r.issue || 'Sem issue') +
    ' · ' +
    esc(r.time) +
    '</small><p>' +
    esc(r.detail) +
    '</p><small>SHA: ' +
    esc(r.sha || 'não fornecido') +
    ' · Correlação: ' +
    esc(r.correlation || 'não fornecida') +
    '</small></div>' +
    (r.url ? ext(r.url, 'Evidência') : '') +
    '</div>'
  );
}
function recordsView() {
  return (
    head(
      'REGISTROS / CONTROLE',
      'Evidências e comandos',
      'Comandos são apenas texto documental; não há execução nem conexão remota.'
    ) +
    '<div class="panel"><div class="between"><div><h3>Registrar evidência verificável</h3><p>Informe o SHA da versão, a fonte e o resultado. Nunca inclua segredos.</p></div><button class="btn primary" data-new="1">+ Novo registro</button></div>' +
    '<div class="notice">Registro no navegador não substitui artefato CAS, issue, TODO Global, log governado ou readback físico.</div><div class="entries">' +
    (records.length
      ? records.slice().reverse().map(item).join('')
      : '<div class="empty">Ainda não há evidências locais.</div>') +
    '</div></div>'
  );
}
function logs() {
  return (
    head(
      'AUDITORIA / HISTÓRICO',
      'Transições e decisões',
      'Registros locais persistem neste dispositivo; é necessário exportar e guardar em destino autorizado.'
    ) +
    '<div class="split"><div class="panel"><div class="between"><h3>Trilha de eventos</h3><button class="btn outline" data-export="1">Exportar JSON + SHA-256</button></div>' +
    (records.length
      ? records.slice().reverse().map(item).join('')
      : '<div class="empty">Nenhuma transição registrada.</div>') +
    '</div>' +
    '<div class="panel"><h3>Requisitos de encerramento</h3><ol class="checks"><li>Pré-condições e SHA do ambiente atual.</li><li>E2E real da mesma tarefa entre dois hosts.</li><li>Negativos, replay e validação independente.</li><li>Readback e evidência do destino.</li><li>TODO Global confirmado e responsabilidade registrada.</li></ol><div class="notice">Exportar JSON não sincroniza TODO Global ou GitHub.</div><p><b>Regras</b><br>v1.6.21 · ' +
    esc(SHA) +
    '</p>' +
    ext(
      'https://github.com/ericson-j-santos/chatgpt-operational-rules/commit/' +
        SHA,
      'Commit canônico'
    ) +
    '</div></div>' +
    (message ? '<p class="message" role="status">' + esc(message) + '</p>' : '')
  );
}
function modal() {
  return (
    '<div class="overlay"><div class="dialog" role="dialog" aria-modal="true" aria-label="Novo registro local"><div class="between"><h3>Registrar evidência ou decisão</h3><button class="close" data-close="1">✕</button></div>' +
    '<form id="register"><div class="form-grid"><label>Tipo<select name="kind"><option>Evidência</option><option>Etapa</option><option>Comando manual</option><option>Decisão</option><option>Log</option><option>Checkpoint</option></select></label><label>Host<select name="host"><option value="">Geral</option>' +
    hosts.map(h => '<option>' + esc(h.name) + '</option>').join('') +
    '</select></label></div>' +
    '<div class="form-grid"><label>Issue<select name="issue"><option value="">Sem issue</option>' +
    tasks.map(t => '<option>' + t.issue + '</option>').join('') +
    '</select></label><label>Etapa<select name="phase"><option value="">Sem etapa</option>' +
    steps
      .map(
        (s, i) =>
          '<option value="' +
          i +
          '">' +
          (i + 1) +
          ' · ' +
          esc(s[0]) +
          '</option>'
      )
      .join('') +
    '</select></label></div>' +
    '<label>Título<input name="title" required maxlength="100" placeholder="Resultado verificável"></label><label>Detalhes / comando documental<textarea name="detail" required maxlength="1800" rows="3" placeholder="Sem tokens ou credenciais"></textarea></label>' +
    '<div class="form-grid"><label>SHA completo<input name="sha" maxlength="64" placeholder="40 caracteres hexadecimais"></label><label>Correlation ID<input name="correlation" maxlength="120" placeholder="Identificador seguro"></label></div>' +
    '<label>URL HTTPS da fonte<input name="url" type="url" maxlength="500" placeholder="https://github.com/..."></label><div class="notice">A gravação modifica apenas o armazenamento local e exige confirmação. Nenhum host será alterado.</div>' +
    '<div class="actions"><button class="btn outline" type="button" data-close="1">Cancelar</button><button class="btn primary" type="submit">Revisar e registrar</button></div></form></div></div>'
  );
}
function render() {
  const current = nav.find(n => n[0] === page) || nav[0];
  root.innerHTML =
    '<div class="shell"><aside class="sidebar"><div class="brand"><span class="brand-icon">R<span>•</span></span><div><b>ReqSys Control</b><small>Recovery & Continuity</small></div></div><p class="nav-label">CENTRAL OPERACIONAL</p><nav>' +
    nav
      .map(
        n =>
          '<button class="nav-item ' +
          (page === n[0] ? 'active' : '') +
          '" data-page="' +
          n[0] +
          '"><span>' +
          n[2] +
          '</span>' +
          n[1] +
          '</button>'
      )
      .join('') +
    '</nav><div class="sidebar-bottom"><b>◈ Modo protegido</b><p>Somente planejamento, registro e validação.</p><small>SEM EXECUÇÃO REMOTA · R$ 0,00</small></div></aside>' +
    '<div class="content"><header class="topbar"><div><small>Operações / ' +
    current[1] +
    '</small><h1>Recuperação e continuidade E2E</h1></div><button class="btn outline" data-export="1">Exportar registros ↗</button></header><main><div class="banner"><span class="circle"></span> DEV · Fontes consultadas em 11/11/2026 · Nenhum host certificado ao vivo ' +
    pill('FAIL-CLOSED', 'amber') +
    '</div>' +
    (page === 'overview'
      ? overview()
      : page === 'queue'
        ? queue()
        : page === 'hosts'
          ? hostsView()
          : page === 'flow'
            ? flow()
            : page === 'records'
              ? recordsView()
              : logs()) +
    '<footer><span>ReqSys — painel documental, não executor</span><span>Regras v1.6.21 · ' +
    SHA.slice(0, 12) +
    '…</span></footer></main></div></div>' +
    (dialog ? modal() : '');
}
function open(opts) {
  preset = opts || {};
  dialog = true;
  render();
  const f = document.getElementById('register');
  if (!f) return;
  if (preset.host) f.elements.host.value = preset.host;
  if (preset.issue) f.elements.issue.value = preset.issue;
  if (Number.isInteger(preset.phase)) {
    f.elements.kind.value = 'Etapa';
    f.elements.phase.value = String(preset.phase);
    f.elements.title.value = 'Evidência — ' + steps[preset.phase][0];
  }
  if (preset.command) {
    f.elements.kind.value = 'Comando manual';
    f.elements.title.value = 'Roteiro governado — ' + preset.host;
    f.elements.detail.value = preset.command;
  }
  f.elements.title.focus();
}
function close() {
  dialog = false;
  render();
}
function submit(form) {
  const f = new FormData(form);
  const val = n => String(f.get(n) || '').trim();
  const title = val('title'),
    detail = val('detail'),
    sha = val('sha'),
    url = val('url');
  if (!title || !detail) {
    alert('Título e detalhes são obrigatórios.');
    return;
  }
  if (sha && !/^[0-9a-fA-F]{40}$/.test(sha)) {
    alert('SHA inválido: exija 40 caracteres hexadecimais.');
    return;
  }
  if (url && !http(url)) {
    alert('A fonte deve ser HTTPS válida.');
    return;
  }
  if (/\b(senha|password|token|secret)\s*[:=]\s*\S+/i.test(detail)) {
    alert('Possível segredo detectado. Remova-o antes de salvar.');
    return;
  }
  if (
    !confirm(
      'CONFIRMA o registro SOMENTE neste navegador? Isso NÃO executa comandos ou altera hosts.'
    )
  )
    return;
  const r = {
    id: 'local-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7),
    time: new Date().toISOString(),
    kind: val('kind'),
    host: val('host'),
    issue: val('issue'),
    phase: val('phase') === '' ? null : Number(val('phase')),
    title,
    detail,
    sha: sha.toLowerCase(),
    url,
    correlation: val('correlation'),
    verification: 'DECLARADO_LOCALMENTE_NAO_VALIDADO',
  };
  records.push(r);
  records = records.slice(-300);
  try {
    localStorage.setItem(KEY, JSON.stringify(records));
  } catch {
    records.pop();
    alert('Sem armazenamento disponível. Registro não confirmado.');
    return;
  }
  dialog = false;
  page = 'records';
  render();
}
async function exportJSON() {
  const raw = JSON.stringify(
    {
      schema: 'reqsys-local-v1',
      exported_at: new Date().toISOString(),
      rules_sha: SHA,
      canonical: false,
      records,
      all_hosts_ready: false,
      cross_host_e2e: false,
    },
    null,
    2
  );
  let hash = 'não calculado';
  try {
    const d = await crypto.subtle.digest(
      'SHA-256',
      new TextEncoder().encode(raw)
    );
    hash = Array.from(new Uint8Array(d))
      .map(v => v.toString(16).padStart(2, '0'))
      .join('');
  } catch {}
  const url = URL.createObjectURL(
    new Blob([raw], { type: 'application/json' })
  );
  const a = document.createElement('a');
  a.href = url;
  a.download = 'reqsys-recuperacao-registros.json';
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 500);
  message =
    'Exportação local solicitada. SHA-256 do JSON: ' +
    hash +
    '. NÃO é readback do TODO Global.';
  page = 'logs';
  render();
}
root.addEventListener('click', e => {
  const x = e.target.closest(
    '[data-page],[data-task],[data-filter],[data-add],[data-host],[data-step],[data-new],[data-export],[data-close]'
  );
  if (!x) return;
  const d = x.dataset;
  if (d.page) {
    page = d.page;
    render();
  } else if (d.task) {
    chosen = d.task;
    page = 'queue';
    render();
  } else if (d.filter) {
    filter = d.filter;
    render();
  } else if (d.add) {
    open({ issue: d.add });
  } else if (d.host) {
    const h = hosts.find(h => h.name === d.host);
    if (h) open({ host: h.name, command: h.command });
  } else if (d.step !== undefined) {
    const i = Number(d.step),
      s = steps[i];
    if (
      confirm(
        'ETAPA ' +
          (i + 1) +
          ': ' +
          s[0] +
          '\n' +
          s[1] +
          '\nBLOQUEIO: ' +
          s[2] +
          '\n\nRegistrar informação LOCAL?'
      )
    )
      open({ phase: i });
  } else if (d.new) {
    open();
  } else if (d.export) {
    exportJSON();
  } else if (d.close) {
    close();
  }
});
root.addEventListener('input', e => {
  if (e.target.id === 'q') {
    query = e.target.value;
    const pos = e.target.selectionStart;
    render();
    const el = document.getElementById('q');
    el.focus();
    el.setSelectionRange(pos, pos);
  }
});
root.addEventListener('submit', e => {
  if (e.target.id === 'register') {
    e.preventDefault();
    submit(e.target);
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && dialog) close();
});
render();
