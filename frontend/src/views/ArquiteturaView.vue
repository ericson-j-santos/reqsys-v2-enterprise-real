<template>
  <section class="page" data-testid="route-arquitetura">
    <div class="page-header">
      <div>
        <h1>Mapa da Solução</h1>
        <p class="muted">Ecossistema ReqSys completo — componentes Web, API, Power Platform e ALM · v3.1.0</p>
      </div>
    </div>

    <v-tabs v-model="aba" color="accent" bg-color="transparent" class="mb-6" density="compact">
      <v-tab value="web">
        <v-icon start size="16">mdi-layers</v-icon>
        ReqSys Web
      </v-tab>
      <v-tab value="lowcode">
        <v-icon start size="16">mdi-microsoft</v-icon>
        Low-Code · Power Platform
      </v-tab>
    </v-tabs>

    <v-window v-model="aba">

      <!-- ══════════════════ ABA: WEB ══════════════════ -->
      <v-window-item value="web">

        <!-- DIAGRAMA DE ARQUITETURA -->
        <div class="arch-diagram">
          <div class="arch-row">
            <div class="arch-label">Usuário</div>
            <div class="arch-nodes">
              <div class="arch-node arch-node--external">
                🌐 Browser<br><small>Chrome / Edge / Firefox</small>
              </div>
              <div class="arch-node arch-node--external">
                🦆 DuckDNS<br><small>tieridev · tierin · tieriprod</small>
              </div>
              <div class="arch-node arch-node--external">
                ✈️ Fly.io CDN<br><small>reqsys-app.fly.dev</small>
              </div>
            </div>
          </div>

          <div class="arch-arrow">↓</div>

          <div class="arch-row">
            <div class="arch-label">Frontend</div>
            <div class="arch-nodes">
              <div class="arch-node arch-node--frontend">
                🖼️ Vue 3 + Vuetify<br><small>10 views · Pinia · Vue Router</small>
              </div>
              <div class="arch-node arch-node--frontend">
                ⚙️ Nginx gateway<br><small>Estático + proxy /api</small>
              </div>
              <div class="arch-node arch-node--frontend">
                🎭 Playwright E2E<br><small>30 testes · 5 suites</small>
              </div>
            </div>
          </div>

          <div class="arch-arrow">↓ &nbsp;HTTPS · Axios · JWT Bearer</div>

          <div class="arch-row">
            <div class="arch-label">Backend</div>
            <div class="arch-nodes">
              <div class="arch-node arch-node--backend">
                🐍 FastAPI Python 3.12<br><small>24 endpoints · JWT · 59 testes Pytest</small>
              </div>
              <div class="arch-node arch-node--backend">
                🔷 .NET 8 / C#<br><small>ASP.NET Core Minimal APIs (evolução)</small>
              </div>
            </div>
          </div>

          <div class="arch-arrow">↓ &nbsp;SQLAlchemy ORM</div>

          <div class="arch-row">
            <div class="arch-label">Dados</div>
            <div class="arch-nodes">
              <div class="arch-node arch-node--data">
                🗃️ SQLite<br><small>/data/reqsys.db · Fly.io volume persistente</small>
              </div>
              <div class="arch-node arch-node--data">
                🏢 SQL Server<br><small>DATABASE_URL configurável (produção)</small>
              </div>
            </div>
          </div>

          <div class="arch-arrow">↕ &nbsp;Graph API · REST</div>

          <div class="arch-row">
            <div class="arch-label">Integrações</div>
            <div class="arch-nodes">
              <div class="arch-node arch-node--integration">
                ⚡ Power Platform<br><small>Hub Low-Code API /v1/hub-lowcode</small>
              </div>
              <div class="arch-node arch-node--integration">
                📊 SharePoint<br><small>IA_Catalogo_Projetos via Graph API</small>
              </div>
              <div class="arch-node arch-node--integration">
                🐙 GitHub ALM<br><small>Runs do repo reqsys-powerplatform-alm</small>
              </div>
              <div class="arch-node arch-node--integration">
                🎨 Figma ↔ GitHub<br><small>Sync bidirecional · /v1/integracoes/figma-github</small>
              </div>
            </div>
          </div>
        </div>

        <!-- VIEWS DO FRONTEND -->
        <div class="subsection-title">
          <v-icon size="15">mdi-application</v-icon>
          Views do Frontend · principais telas
        </div>
        <v-row>
          <v-col
            v-for="view in webViews"
            :key="view.rota"
            cols="12" sm="6" md="4" lg="3"
          >
            <v-card class="comp-card" elevation="0">
              <v-card-text class="pa-3">
                <div class="d-flex align-center gap-2 mb-1">
                  <v-icon :color="view.cor" size="16">{{ view.icone }}</v-icon>
                  <span class="comp-name">{{ view.nome }}</span>
                </div>
                <code class="comp-rota">{{ view.rota }}</code>
                <div class="comp-desc mt-1">{{ view.desc }}</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- MÓDULOS BACKEND -->
        <div class="subsection-title mt-6">
          <v-icon size="15">mdi-api</v-icon>
          Módulos do Backend · FastAPI · 24 endpoints validados
        </div>
        <v-row>
          <v-col
            v-for="mod in backendModulos"
            :key="mod.prefixo"
            cols="12" sm="6" md="4"
          >
            <v-card class="comp-card" elevation="0">
              <v-card-text class="pa-3">
                <div class="d-flex align-center gap-2 mb-1">
                  <v-chip size="x-small" color="primary" variant="tonal">{{ mod.endpoints }} ep</v-chip>
                  <span class="comp-name">{{ mod.nome }}</span>
                </div>
                <code class="comp-rota">{{ mod.prefixo }}</code>
                <div class="comp-desc mt-1">{{ mod.desc }}</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- AMBIENTES FLY.IO -->
        <div class="subsection-title mt-6">
          <v-icon size="15">mdi-cloud-outline</v-icon>
          Ambientes · Fly.io · Região GRU (São Paulo)
        </div>
        <v-table density="compact" class="env-table mb-4">
          <thead>
            <tr>
              <th>Ambiente</th>
              <th>Frontend</th>
              <th>Backend API</th>
              <th>DuckDNS</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="env in ambientesFlyio"
              :key="env.id"
              class="ambiente-row"
              tabindex="0"
              role="link"
              :aria-label="`Abrir ambiente ${env.label}`"
              :data-testid="`ambiente-linha-${env.shortId}`"
              @click="abrirAmbienteFlyio(env.id)"
              @keydown.enter.prevent="abrirAmbienteFlyio(env.id)"
              @keydown.space.prevent="abrirAmbienteFlyio(env.id)"
            >
              <td><v-chip size="x-small" :color="env.color" variant="tonal">{{ env.label }}</v-chip></td>
              <td><code class="small-code">{{ env.frontendHost }}</code></td>
              <td><code class="small-code">{{ env.backendHost }}</code></td>
              <td><code class="small-code">{{ env.duckdnsHost }}</code></td>
            </tr>
          </tbody>
        </v-table>

        <!-- TESTES -->
        <div class="subsection-title mt-4">
          <v-icon size="15">mdi-test-tube</v-icon>
          Cobertura de Testes
        </div>
        <v-row>
          <v-col cols="12" sm="6" md="4">
            <v-card class="comp-card" elevation="0">
              <v-card-text class="pa-3">
                <div class="d-flex align-center gap-2 mb-2">
                  <v-icon color="success" size="16">mdi-check-circle</v-icon>
                  <span class="comp-name">Backend · Pytest</span>
                  <v-chip size="x-small" color="success" variant="tonal">59 passing</v-chip>
                </div>
                <div class="muted" style="font-size:11px">test_auth · test_requisitos · test_dashboard</div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-card class="comp-card" elevation="0">
              <v-card-text class="pa-3">
                <div class="d-flex align-center gap-2 mb-2">
                  <v-icon color="success" size="16">mdi-check-circle</v-icon>
                  <span class="comp-name">Frontend · E2E Playwright</span>
                  <v-chip size="x-small" color="success" variant="tonal">30 passing</v-chip>
                </div>
                <div class="muted" style="font-size:11px">login · dashboard · relatórios · requisitos · segredos</div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-card class="comp-card" elevation="0">
              <v-card-text class="pa-3">
                <div class="d-flex align-center gap-2 mb-2">
                  <v-icon color="info" size="16">mdi-code-braces</v-icon>
                  <span class="comp-name">Backend .NET · xUnit</span>
                  <v-chip size="x-small" color="info" variant="tonal">em evolução</v-chip>
                </div>
                <div class="muted" style="font-size:11px">dotnet test ReqSys.DotNet.sln</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- README EXEC RÁPIDA -->
        <div class="subsection-title mt-6">
          <v-icon size="15">mdi-console</v-icon>
          Execução Rápida
        </div>
        <v-row>
          <v-col cols="12" md="6">
            <v-card class="comp-card" elevation="0">
              <v-card-title class="pa-3 pb-1" style="font-size:13px;font-weight:700">Backend</v-card-title>
              <v-card-text class="pa-3 pt-1">
                <pre class="code-block">cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload</pre>
                <div class="muted mt-2" style="font-size:11px">Porta 8000 · docs em /docs</div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" md="6">
            <v-card class="comp-card" elevation="0">
              <v-card-title class="pa-3 pb-1" style="font-size:13px;font-weight:700">Frontend</v-card-title>
              <v-card-text class="pa-3 pt-1">
                <pre class="code-block">cd frontend
npm install
npm run dev</pre>
                <div class="muted mt-2" style="font-size:11px">Porta 5173 · Vite HMR</div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" md="6">
            <v-card class="comp-card" elevation="0">
              <v-card-title class="pa-3 pb-1" style="font-size:13px;font-weight:700">Docker (prod local)</v-card-title>
              <v-card-text class="pa-3 pt-1">
                <pre class="code-block">docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  up --build -d</pre>
                <div class="muted mt-2" style="font-size:11px">Gateway nginx na porta 8081</div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" md="6">
            <v-card class="comp-card" elevation="0">
              <v-card-title class="pa-3 pb-1" style="font-size:13px;font-weight:700">Deploy Fly.io</v-card-title>
              <v-card-text class="pa-3 pt-1">
                <pre class="code-block">.\scripts\fly-deploy.ps1 -Env prod
# ou: -Env dev | -Env staging</pre>
                <div class="muted mt-2" style="font-size:11px">Requer flyctl autenticado</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

      </v-window-item>


      <!-- ══════════════════ ABA: LOW-CODE ══════════════════ -->
      <v-window-item value="lowcode">

        <!-- DIAGRAMA DE FLUXO -->
        <div class="flow-diagram">
          <div class="flow-node flow-node--user">
            👤 Usuário<br><small>Teams ou Web</small>
          </div>
          <div class="flow-connector">→</div>
          <div class="flow-node flow-node--bot">
            🤖 ReqSysAgent<br><small>Copilot Studio</small>
          </div>
          <div class="flow-connector">→</div>
          <div class="flow-node flow-node--flow">
            ⚡ Criar no Planner<br><small>Power Automate</small>
          </div>
          <div class="flow-connector">→</div>
          <div class="flow-node flow-node--planner">
            📋 Microsoft Planner<br><small>Tarefas criadas</small>
          </div>
        </div>
        <div class="flow-label muted mt-1 mb-4">
          Tópico "Capturar Tarefas" → InvokeFlowAction → ForEach linha → Create Task Planner
        </div>

        <div class="flow-diagram mt-2">
          <div class="flow-node flow-node--user">
            👤 Designer / PO<br><small>Teams, Web ou Figma</small>
          </div>
          <div class="flow-connector">→</div>
          <div class="flow-node flow-node--bot">
            🤖 ReqSysAgent<br><small>Tópico Sincronizar Figma</small>
          </div>
          <div class="flow-connector">→</div>
          <div class="flow-node flow-node--flow">
            ⚡ ReqSys API<br><small>POST /figma-github/sync</small>
          </div>
          <div class="flow-connector">→</div>
          <div class="flow-node flow-node--planner">
            🐙 GitHub Issues<br><small>Issues e comentários vinculados</small>
          </div>
        </div>
        <div class="flow-label muted mt-1 mb-4">
          Tópico "Sincronizar Figma GitHub" → API ReqSys → vínculos Figma/GitHub auditáveis em /figma-github
        </div>

        <!-- COMPONENTES DA SOLUTION -->
        <div class="subsection-title">
          <v-icon size="15">mdi-puzzle</v-icon>
          Componentes da Solution · ReqSysAutomacao
        </div>
        <v-row>
          <v-col
            v-for="comp in solutionComps"
            :key="comp.nome"
            cols="12" sm="6" md="4"
          >
            <v-card class="comp-card" elevation="0">
              <v-card-text class="pa-3">
                <div class="d-flex align-center gap-2 mb-1">
                  <v-icon :color="comp.cor" size="16">{{ comp.icone }}</v-icon>
                  <span class="comp-name">{{ comp.nome }}</span>
                </div>
                <div class="comp-rota muted">{{ comp.tipo }}</div>
                <div class="comp-desc mt-1">{{ comp.desc }}</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- ALM PIPELINE -->
        <div class="subsection-title mt-6">
          <v-icon size="15">mdi-source-branch</v-icon>
          Pipeline ALM · GitHub Actions · ericson-j-santos/reqsys-powerplatform-alm
        </div>
        <div class="pipeline-flow mb-4">
          <div
            v-for="(step, i) in almPipeline"
            :key="step.nome"
            class="d-flex align-center"
          >
            <div class="pipeline-step">
              <v-icon :color="step.cor" size="20">{{ step.icone }}</v-icon>
              <div class="pipeline-nome">{{ step.nome }}</div>
              <div class="muted pipeline-desc">{{ step.desc }}</div>
            </div>
            <div v-if="i < almPipeline.length - 1" class="pipeline-arrow">→</div>
          </div>
        </div>
        <div class="muted mb-6" style="font-size:11px;padding-left:4px">
          Workflow de exportação cria PR automaticamente → merge dispara deploy em Build/Test → aprovação em main → Prod + GitHub Release
        </div>

        <!-- AMBIENTES DATAVERSE -->
        <div class="subsection-title">
          <v-icon size="15">mdi-database-outline</v-icon>
          Ambientes Dataverse · 4 ambientes
        </div>
        <v-table density="compact" class="env-table mb-6">
          <thead>
            <tr><th>Slug</th><th>URL Org</th><th>Papel no ALM</th></tr>
          </thead>
          <tbody>
            <tr v-for="env in dataverseEnvs" :key="env.slug">
              <td><v-chip size="x-small" :color="env.cor" variant="tonal">{{ env.slug }}</v-chip></td>
              <td><code class="small-code">{{ env.url }}</code></td>
              <td class="muted" style="font-size:11px">{{ env.papel }}</td>
            </tr>
          </tbody>
        </v-table>

        <!-- HUB LOW-CODE API -->
        <div class="subsection-title">
          <v-icon size="15">mdi-api</v-icon>
          Hub Low-Code API · Ponte ReqSys Web ↔ Power Platform
        </div>
        <v-row class="mb-6">
          <v-col
            v-for="ep in hubEndpoints"
            :key="ep.rota"
            cols="12" sm="6" md="3"
          >
            <v-card class="comp-card" elevation="0">
              <v-card-text class="pa-3">
                <v-chip size="x-small" color="success" variant="tonal" class="mb-2">GET</v-chip>
                <div class="comp-name">{{ ep.rota }}</div>
                <div class="comp-desc mt-1">{{ ep.desc }}</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- SHAREPOINT E SPN -->
        <div class="subsection-title">
          <v-icon size="15">mdi-shield-account</v-icon>
          SharePoint · Graph API · SPN
        </div>
        <v-row>
          <v-col cols="12" sm="6" md="4">
            <v-card class="comp-card" elevation="0">
              <v-card-text class="pa-3">
                <div class="d-flex align-center gap-2 mb-2">
                  <v-icon color="warning" size="16">mdi-microsoft-sharepoint</v-icon>
                  <span class="comp-name">IA_Catalogo_Projetos</span>
                </div>
                <div class="muted" style="font-size:11px">Lista SharePoint · tieri659.sharepoint.com</div>
                <div class="comp-desc mt-1">Catálogo de projetos IA. Lido por /hub-lowcode/pacotes via Graph API.</div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-card class="comp-card" elevation="0">
              <v-card-text class="pa-3">
                <div class="d-flex align-center gap-2 mb-2">
                  <v-icon color="info" size="16">mdi-key-chain-variant</v-icon>
                  <span class="comp-name">SPN cb8c924f</span>
                </div>
                <div class="muted" style="font-size:11px">Service Principal · tenant 6d09c88c</div>
                <div class="comp-desc mt-1">Administrador nos 4 ambientes. 3 permissões Graph API: Sites.Read.All · Sites.ReadWrite.All · Sites.Manage.All</div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-card class="comp-card" elevation="0">
              <v-card-text class="pa-3">
                <div class="d-flex align-center gap-2 mb-2">
                  <v-icon color="success" size="16">mdi-microsoft-teams</v-icon>
                  <span class="comp-name">Teams · Canal ativo</span>
                </div>
                <div class="muted" style="font-size:11px">Bot ReqSysAgent instalado e publicado</div>
                <div class="comp-desc mt-1">Usuários conversam com o bot no Teams para capturar e criar tarefas no Planner.</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- README EXEC SCRIPTS -->
        <div class="subsection-title mt-6">
          <v-icon size="15">mdi-console</v-icon>
          Scripts de Operação
        </div>
        <v-row>
          <v-col cols="12" sm="6" md="4" v-for="script in scripts" :key="script.nome">
            <v-card class="comp-card" elevation="0">
              <v-card-text class="pa-3">
                <div class="comp-name mb-1">{{ script.nome }}</div>
                <pre class="code-block">{{ script.cmd }}</pre>
                <div class="comp-desc mt-1">{{ script.desc }}</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

      </v-window-item>
    </v-window>

    <ConfirmacaoAmbienteProducaoDialog
      v-model="confirmacaoProdAberta"
      :url="destinoPendente?.url || ''"
      @confirmar="confirmarNavegacaoProd"
      @cancelar="cancelarNavegacaoProd"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import ConfirmacaoAmbienteProducaoDialog from '../components/ConfirmacaoAmbienteProducaoDialog.vue'
import { useNavegacaoAmbiente } from '../composables/useNavegacaoAmbiente'
import { AMBIENTES_OPERACIONAIS } from '../constants/ambientesOperacionais'

const aba = ref('web')

const webViews = [
  { nome: 'Dashboard',       rota: '/',                icone: 'mdi-view-dashboard',          cor: 'secondary', desc: 'KPIs consolidados, cards de métricas e pipeline operacional' },
  { nome: 'Requisitos',      rota: '/requisitos',      icone: 'mdi-file-document-edit',      cor: 'primary',   desc: 'CRUD de requisitos com status, urgência, área e sistema' },
  { nome: 'Pipeline',        rota: '/pipeline',        icone: 'mdi-pipe',                    cor: 'info',      desc: 'Fluxo Entrada → Normalização → Estruturação → Publicação' },
  { nome: 'Task Console',    rota: '/task-console',    icone: 'mdi-clipboard-check-outline', cor: 'accent',    desc: 'Revisar tarefas e preparar envio para o Planner' },
  { nome: 'Qualidade IA',    rota: '/qualidade-ia',    icone: 'mdi-brain',                   cor: 'deep-purple', desc: 'Score, tendência histórica e recomendações do módulo de IA' },
  { nome: 'Relatórios SSRS', rota: '/relatorios',      icone: 'mdi-file-chart-outline',      cor: 'success',   desc: 'Catálogo e status dos relatórios SSRS do servidor NOTERI' },
  { nome: 'Segredos',        rota: '/segredos-status', icone: 'mdi-key-chain-variant',       cor: 'warning',   desc: 'Diagnóstico da origem de cada segredo (env / cofre / padrão)' },
  { nome: 'Rastreabilidade', rota: '/rastreabilidade', icone: 'mdi-vector-link',             cor: 'indigo',    desc: 'Matriz Requisito → História → Issue Redmine → Commit Git' },
  { nome: 'Specs SDD',       rota: '/specs',           icone: 'mdi-file-code-outline',       cor: 'deep-orange', desc: 'Especificações de features do my-first-spec-project (.sdd)' },
  { nome: 'Auditoria',       rota: '/auditoria',       icone: 'mdi-shield-search',           cor: 'error',     desc: 'Linha do tempo de eventos, correlation_id e governança' },
  { nome: 'Figma GitHub',    rota: '/figma-github',    icone: 'mdi-vector-square',           cor: 'pink',      desc: 'Sincronização governada Figma ↔ GitHub com retorno em tela e tabela analítica' },
  { nome: 'Hub Low-Code',    rota: '/hub-lowcode',     icone: 'mdi-lightning-bolt-circle',   cor: 'teal',      desc: 'Pacotes IA, flows Power Automate, bot ReqSysAgent e pipeline GitHub ALM' },
  { nome: 'Monitoramento',   rota: '/monitoramento-operacional', icone: 'mdi-monitor-dashboard', cor: 'cyan', desc: 'Estado operacional de PRs, gates, integrações e pendências' },
]

const backendModulos = [
  { nome: 'Autenticação',    prefixo: '/v1/auth',           endpoints: '1',  desc: 'Login por e-mail, JWT com papel (admin / analista)' },
  { nome: 'Sistema',         prefixo: '/v1/sistema',        endpoints: '5',  desc: 'Health check, versão, endpoints, segredos-status, cofre' },
  { nome: 'Dashboard',       prefixo: '/v1/dashboard',      endpoints: '2',  desc: 'KPIs de requisitos e informações gerais' },
  { nome: 'Requisitos',      prefixo: '/v1/requisitos',     endpoints: '3',  desc: 'CRUD, validação de payload e registro de solicitações' },
  { nome: 'Qualidade IA',    prefixo: '/v1/qualidade-ia',   endpoints: '5',  desc: 'Resumo, tendência, export CSV/PDF e snapshot manual' },
  { nome: 'Auditoria',       prefixo: '/v1/auditoria',      endpoints: '2',  desc: 'Eventos de auditoria e configuração de infra' },
  { nome: 'Cofre',           prefixo: '/v1/cofre',          endpoints: '6',  desc: 'Cofre local AES-GCM: init, status, gravar, remover e resolver segredos' },
  { nome: 'Specs SDD',       prefixo: '/v1/specs',          endpoints: '3',  desc: 'Features, exemplos e templates de especificação' },
  { nome: 'Relatórios SSRS', prefixo: '/v1/relatorios',     endpoints: '3',  desc: 'Catálogo, status e health do servidor SSRS NOTERI' },
  { nome: 'Hub Low-Code',    prefixo: '/v1/hub-lowcode',    endpoints: '4',  desc: 'Status, pacotes SharePoint, flows Dataverse, runs GitHub' },
  { nome: 'Figma GitHub',    prefixo: '/v1/integracoes/figma-github', endpoints: '2', desc: 'Sync bidirecional Figma ↔ GitHub e consulta de vínculos em tela' },
]

const ambientesFlyio = computed(() =>
  AMBIENTES_OPERACIONAIS.filter((item) => !item.onlyLocal).map((item) => ({
    ...item,
    frontendHost: item.frontend.replace(/^https?:\/\//, ''),
    backendHost: item.backend.replace(/^https?:\/\//, ''),
    duckdnsHost: item.duckdns.replace(/^https?:\/\//, ''),
  })),
)

const {
  confirmacaoProdAberta,
  destinoPendente,
  solicitarNavegacao,
  confirmarNavegacaoProd,
  cancelarNavegacaoProd,
} = useNavegacaoAmbiente()

function abrirAmbienteFlyio(id) {
  solicitarNavegacao(id, { path: '/arquitetura', preserveRoute: false })
}

const solutionComps = [
  {
    nome: 'ReqSysAgent',          tipo: 'Bot · Copilot Studio',
    icone: 'mdi-robot',           cor: 'deep-purple',
    desc:  'Publicado e instalado no Teams. Bot ID: 5109ed0f-fe65-f111-ab0c-7ced8da7c8da',
  },
  {
    nome: 'Capturar Tarefas',     tipo: 'Tópico · Bot',
    icone: 'mdi-comment-text',    cor: 'indigo',
    desc:  'Coleta linhas de tarefa → confirmação → InvokeFlowAction → informa resultado',
  },
  {
    nome: 'Sincronizar Figma GitHub', tipo: 'Tópico · Bot',
    icone: 'mdi-vector-square',   cor: 'pink',
    desc:  'Aciona sync Figma ↔ GitHub via API ReqSys e orienta consulta em /figma-github',
  },
  {
    nome: 'Criar no Planner',     tipo: 'Flow · Power Automate',
    icone: 'mdi-lightning-bolt',  cor: 'primary',
    desc:  'Trigger PowerAppsV2. ForEach linha → Create Task Planner. ID: 73bd346b-c765-f111',
  },
  {
    nome: 'reqsys_shared_planner',tipo: 'Connection Reference',
    icone: 'mdi-link',            cor: 'cyan',
    desc:  'Referência de conexão do conector Planner usada pelo flow',
  },
  {
    nome: 'Variáveis de Ambiente',tipo: '4 env vars · Dataverse',
    icone: 'mdi-cog-outline',     cor: 'success',
    desc:  'reqsys_EquipeId · reqsys_CanalId · reqsys_GrupoId · reqsys_PlanoId',
  },
  {
    nome: 'ReqSysAutomacao',      tipo: 'Solution · 17 componentes',
    icone: 'mdi-package-variant', cor: 'warning',
    desc:  'Solution exportada e versionada no GitHub. Bot + Flow + 15 botcomponents',
  },
]

const almPipeline = [
  { nome: 'Dev (tieri)', icone: 'mdi-pencil',          cor: 'primary', desc: 'Editar bot ou flow no Copilot Studio / Power Apps' },
  { nome: 'Export',      icone: 'mdi-export',          cor: 'info',    desc: 'pac solution export → unpack → PR automático' },
  { nome: 'Build',       icone: 'mdi-package-variant', cor: 'warning', desc: 'pack → import Build env → export managed' },
  { nome: 'Test',        icone: 'mdi-test-tube',       cor: 'orange',  desc: 'Deploy automático em Test após merge do PR' },
  { nome: 'Prod',        icone: 'mdi-rocket-launch',   cor: 'success', desc: 'Merge em main → deploy Prod + GitHub Release' },
]

const dataverseEnvs = [
  { slug: 'reqsys-dev',   url: 'orga258f260.crm2.dynamics.com', papel: 'Desenvolvimento · mesmo ambiente tieri default', cor: 'primary' },
  { slug: 'reqsys-build', url: 'org4ee98db6.crm2.dynamics.com', papel: 'Empacotamento e build da solution gerenciada',   cor: 'info'    },
  { slug: 'reqsys-test',  url: 'orgf2ca7436.crm2.dynamics.com', papel: 'Testes automatizados E2E do ALM',                cor: 'warning' },
  { slug: 'reqsys-prod',  url: 'org2dd77e2a.crm2.dynamics.com', papel: 'Produção Power Platform',                        cor: 'success' },
]

const hubEndpoints = [
  { rota: '/status',   desc: 'Resumo consolidado do hub (card no Dashboard ReqSys Web)' },
  { rota: '/pacotes',  desc: 'Catálogo IA da lista SharePoint IA_Catalogo_Projetos' },
  { rota: '/flows',    desc: '11 flows Dataverse + execuções do flow principal Planner' },
  { rota: '/github',   desc: 'Últimos 10 runs do GitHub Actions do repo ALM' },
]

const scripts = [
  {
    nome: 'Exportar para ALM',
    cmd:  '.\\scripts\\05-primeiro-export.ps1',
    desc: 'Exporta solution do Dev, desempacota e cria PR no GitHub',
  },
  {
    nome: 'Testes E2E Power Platform',
    cmd:  '.\\scripts\\test-e2e.ps1',
    desc: '5 testes E2E integrados. Use -CriarTarefaTeste para escrever no Planner',
  },
  {
    nome: 'Dashboard em tempo real',
    cmd:  '.\\scripts\\gerar-dashboard.ps1',
    desc: 'Gera dashboard.html com dados do flow, bot e tarefas Planner',
  },
]
</script>

<style scoped>
/* ─── Architecture Diagram ─── */
.arch-diagram {
  background: var(--card-alt);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 32px;
}

.arch-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 6px 0;
}

.arch-label {
  width: 90px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--muted);
  flex-shrink: 0;
  text-align: right;
}

.arch-nodes {
  display: flex;
  gap: 10px;
  flex: 1;
  flex-wrap: wrap;
}

.arch-node {
  flex: 1;
  min-width: 140px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  text-align: center;
  line-height: 1.4;
}

.arch-node small {
  display: block;
  font-weight: 400;
  font-size: 10px;
  margin-top: 2px;
}

.arch-node--external    { background: rgba(100,100,100,.1); border: 1px solid rgba(100,100,100,.25); }
.arch-node--frontend    { background: rgba(0,92,169,.1);    border: 1px solid rgba(0,92,169,.3);     }
.arch-node--backend     { background: rgba(243,146,0,.1);   border: 1px solid rgba(243,146,0,.3);    }
.arch-node--data        { background: rgba(0,179,173,.1);   border: 1px solid rgba(0,179,173,.3);    }
.arch-node--integration { background: rgba(46,125,50,.1);   border: 1px solid rgba(46,125,50,.3);    }

.arch-arrow {
  padding: 2px 0 2px 106px;
  color: var(--muted);
  font-size: 11px;
}

/* ─── Flow Diagram ─── */
.flow-diagram {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 0;
  background: var(--card-alt);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 6px;
}

.flow-label {
  text-align: center;
  font-size: 11px;
}

.flow-node {
  text-align: center;
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
  min-width: 130px;
}

.flow-node small {
  display: block;
  font-weight: 400;
  font-size: 10px;
  margin-top: 2px;
}

.flow-connector {
  padding: 0 10px;
  color: var(--muted);
  font-size: 20px;
  font-weight: 300;
}

.flow-node--user    { background: rgba(99,102,241,.12);  border: 1px solid rgba(99,102,241,.35);  }
.flow-node--bot     { background: rgba(168,85,247,.12);  border: 1px solid rgba(168,85,247,.35);  }
.flow-node--flow    { background: rgba(0,92,169,.12);    border: 1px solid rgba(0,92,169,.35);    }
.flow-node--planner { background: rgba(0,179,173,.12);   border: 1px solid rgba(0,179,173,.35);   }

/* ─── ALM Pipeline ─── */
.pipeline-flow {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0;
  background: var(--card-alt);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 20px;
}

.pipeline-step {
  text-align: center;
  padding: 8px 14px;
  min-width: 90px;
}

.pipeline-nome {
  font-size: 11px;
  font-weight: 700;
  margin-top: 4px;
}

.pipeline-desc {
  font-size: 10px;
  margin-top: 2px;
  max-width: 100px;
}

.pipeline-arrow {
  display: flex;
  align-items: center;
  color: var(--muted);
  font-size: 16px;
  padding: 0 2px;
}

/* ─── Component Cards ─── */
.comp-card {
  height: 100%;
  background: var(--card) !important;
}

.comp-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.comp-rota {
  font-size: 11px;
  font-family: 'Consolas', 'Fira Code', monospace;
  color: var(--muted);
}

.comp-desc {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.4;
}

/* ─── Subsection Title ─── */
.subsection-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--muted);
  margin-bottom: 10px;
  padding-left: 2px;
  border-left: 3px solid var(--accent);
  padding-left: 8px;
}

/* ─── Tables ─── */
.env-table {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.env-table .ambiente-row {
  cursor: pointer;
  transition: background 0.15s ease;
}

.env-table .ambiente-row:hover {
  background: rgba(245, 158, 11, 0.08);
}

.env-table .ambiente-row:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

/* ─── Code blocks ─── */
.code-block {
  background: var(--card-alt);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 11px;
  font-family: 'Consolas', 'Fira Code', monospace;
  white-space: pre-wrap;
  margin: 0;
  line-height: 1.6;
  color: var(--accent-strong);
}

.small-code {
  font-size: 10px;
  font-family: 'Consolas', monospace;
  color: var(--muted);
}

/* ─── Responsive ─── */
@media (max-width: 600px) {
  .arch-nodes {
    flex-direction: column;
  }
  .flow-diagram {
    flex-direction: column;
    gap: 6px;
  }
  .flow-connector {
    transform: rotate(90deg);
    font-size: 14px;
    padding: 2px 0;
  }
  .pipeline-flow {
    flex-direction: column;
  }
  .pipeline-arrow {
    transform: rotate(90deg);
  }
}
</style>
