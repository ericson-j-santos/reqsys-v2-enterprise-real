<template>
  <section class="page governance-page" data-testid="route-governanca">
    <div class="page-header governance-hero">
      <div>
        <div class="eyebrow">Padrão Ouro Enterprise</div>
        <h1>Governança, Qualidade e Arquitetura Viva</h1>
        <p class="muted">
          Portal navegável para transformar os padrões documentais do ReqSys em uma visão operacional de governança, CI/CD, segurança, observabilidade, analytics e IA auditável.
        </p>
      </div>
      <div class="hero-actions">
        <v-chip color="success" variant="tonal" size="small">Publicado no frontend</v-chip>
        <v-chip color="info" variant="tonal" size="small">Rota /governanca</v-chip>
      </div>
    </div>

    <v-row class="mb-4">
      <v-col v-for="kpi in kpis" :key="kpi.titulo" cols="12" sm="6" md="3">
        <v-card class="metric-card" elevation="0">
          <v-card-text>
            <div class="metric-label">{{ kpi.titulo }}</div>
            <div class="metric-value">{{ kpi.valor }}</div>
            <div class="metric-desc">{{ kpi.desc }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-tabs v-model="aba" color="accent" bg-color="transparent" density="compact" class="mb-5">
      <v-tab value="ciclo">Ciclo</v-tab>
      <v-tab value="gates">Gates</v-tab>
      <v-tab value="observabilidade">Observabilidade</v-tab>
      <v-tab value="analytics">Analytics</v-tab>
      <v-tab value="ia">IA Auditável</v-tab>
      <v-tab value="ambientes">Ambientes</v-tab>
    </v-tabs>

    <v-window v-model="aba">
      <v-window-item value="ciclo">
        <v-card class="section-card" elevation="0">
          <v-card-title>Ciclo operacional obrigatório</v-card-title>
          <v-card-text>
            <div class="flow-line">
              <div v-for="(step, index) in ciclo" :key="step" class="flow-step">
                <div class="step-index">{{ index + 1 }}</div>
                <div class="step-title">{{ step }}</div>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-window-item>

      <v-window-item value="gates">
        <v-row>
          <v-col v-for="gate in gates" :key="gate.titulo" cols="12" md="6">
            <v-card class="gate-card" elevation="0">
              <v-card-text>
                <div class="d-flex align-center gap-2 mb-2">
                  <v-icon color="error" size="18">mdi-alert-octagon</v-icon>
                  <strong>{{ gate.titulo }}</strong>
                </div>
                <p class="muted mb-0">{{ gate.desc }}</p>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-window-item>

      <v-window-item value="observabilidade">
        <v-card class="section-card" elevation="0">
          <v-card-title>Observabilidade mínima</v-card-title>
          <v-card-text>
            <v-table density="compact" class="governance-table">
              <thead>
                <tr><th>Capacidade</th><th>Padrão</th><th>Uso operacional</th></tr>
              </thead>
              <tbody>
                <tr v-for="item in observabilidade" :key="item.capacidade">
                  <td><strong>{{ item.capacidade }}</strong></td>
                  <td>{{ item.padrao }}</td>
                  <td>{{ item.uso }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-window-item>

      <v-window-item value="analytics">
        <v-card class="section-card" elevation="0">
          <v-card-title>Fluxo analítico navegável</v-card-title>
          <v-card-text>
            <div class="analytics-flow">
              <div v-for="item in analytics" :key="item" class="analytics-node">{{ item }}</div>
            </div>
            <p class="muted mt-4 mb-0">
              Cards, gráficos e indicadores devem abrir o analítico correspondente já filtrado, preservando ambiente, usuário, permissão e rastreabilidade.
            </p>
          </v-card-text>
        </v-card>
      </v-window-item>

      <v-window-item value="ia">
        <v-row>
          <v-col v-for="item in iaAuditavel" :key="item.titulo" cols="12" md="4">
            <v-card class="ia-card" elevation="0">
              <v-card-text>
                <v-icon color="deep-purple" size="22" class="mb-2">{{ item.icone }}</v-icon>
                <div class="card-title">{{ item.titulo }}</div>
                <p class="muted mb-0">{{ item.desc }}</p>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-window-item>

      <v-window-item value="ambientes">
        <v-card class="section-card" elevation="0">
          <v-card-title>Ambientes e URLs operacionais</v-card-title>
          <v-card-text>
            <v-table density="compact" class="governance-table">
              <thead>
                <tr><th>Ambiente</th><th>Frontend</th><th>Backend</th><th>Uso</th></tr>
              </thead>
              <tbody>
                <tr
                  v-for="env in ambientes"
                  :key="env.id"
                  class="ambiente-row"
                  tabindex="0"
                  role="link"
                  :aria-label="`Abrir ambiente ${env.label}`"
                  :data-testid="`ambiente-linha-${env.shortId}`"
                  @click="abrirAmbiente(env.id)"
                  @keydown.enter.prevent="abrirAmbiente(env.id)"
                  @keydown.space.prevent="abrirAmbiente(env.id)"
                >
                  <td><v-chip :color="env.color" variant="tonal" size="x-small">{{ env.label }}</v-chip></td>
                  <td><code>{{ env.frontend }}</code></td>
                  <td><code>{{ env.backend }}</code></td>
                  <td>{{ env.uso }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
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

const aba = ref('ciclo')

const ambientes = computed(() =>
  AMBIENTES_OPERACIONAIS.filter((item) => !item.onlyLocal).map((item) => ({
    ...item,
    frontend: `${item.frontend}/governanca`,
    backend: item.backend,
  })),
)

const {
  confirmacaoProdAberta,
  destinoPendente,
  solicitarNavegacao,
  confirmarNavegacaoProd,
  cancelarNavegacaoProd,
} = useNavegacaoAmbiente()

function abrirAmbiente(id) {
  solicitarNavegacao(id, { path: '/governanca', preserveRoute: false })
}

const kpis = [
  { titulo: 'Baseline', valor: '100%', desc: 'Governança padrão ouro documentada e navegável.' },
  { titulo: 'Gates', valor: '11', desc: 'Condições bloqueantes para produção.' },
  { titulo: 'Rastreio', valor: 'E2E', desc: 'Requisito → PR → CI → produção → monitoramento.' },
  { titulo: 'Publicação', valor: '/governanca', desc: 'Rota dedicada no frontend ReqSys.' },
]

const ciclo = ['Planejar', 'Versionar', 'Implementar', 'Testar', 'Validar CI', 'Revisar', 'Publicar', 'Monitorar', 'Documentar', 'Evoluir']

const gates = [
  { titulo: 'Auth desligada', desc: 'Produção bloqueada se autenticação estiver desativada ou relaxada.' },
  { titulo: 'CORS inseguro', desc: 'Produção bloqueada se CORS aceitar origem ampla com wildcard.' },
  { titulo: 'JWT frágil', desc: 'Produção bloqueada sem validação real de issuer, audience e claims.' },
  { titulo: 'Segredos expostos', desc: 'Produção bloqueada se logs ou código contiverem tokens, senhas, CPF, PII ou connection string.' },
  { titulo: 'IA sem fonte', desc: 'Consulta de IA/RAG deve ter fonte, confiança e fallback seguro.' },
  { titulo: 'CI vermelho', desc: 'Merge e deploy bloqueados quando build, testes ou validações falharem.' },
]

const observabilidade = [
  { capacidade: 'Logs JSON', padrao: 'Estruturados e sem PII', uso: 'Auditoria, suporte e análise de incidentes.' },
  { capacidade: 'correlation_id', padrao: 'Obrigatório por request', uso: 'Rastrear fluxo ponta a ponta.' },
  { capacidade: 'Métricas', padrao: 'Latência, erro, throughput, integrações', uso: 'Painéis e alertas operacionais.' },
  { capacidade: 'Tracing', padrao: 'OpenTelemetry como evolução', uso: 'Fluxo runtime e arquitetura viva.' },
]

const analytics = ['Indicador', 'Gráfico', 'Analítico filtrado', 'Detalhe', 'Log correlacionado', 'Ação operacional']

const iaAuditavel = [
  { icone: 'mdi-database-search', titulo: 'Fontes obrigatórias', desc: 'Toda resposta baseada em dados deve apresentar origem rastreável.' },
  { icone: 'mdi-shield-check', titulo: 'Confiança e fallback', desc: 'Quando não houver evidência suficiente, a IA deve sinalizar incerteza e evitar resposta inventada.' },
  { icone: 'mdi-clipboard-text-clock', titulo: 'Auditoria', desc: 'Pergunta, resposta, fonte, usuário, ambiente e correlation_id devem ser registrados.' },
]

</script>

<style scoped>
.governance-page { min-width: 0; }
.governance-hero { align-items: flex-start; gap: 16px; }
.eyebrow { color: var(--accent); font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 4px; }
.hero-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.metric-card, .section-card, .gate-card, .ia-card { border: 1px solid rgba(148, 163, 184, .22); border-radius: 14px; background: rgba(15, 23, 42, .02); }
.metric-label { font-size: 12px; color: var(--muted); font-weight: 700; }
.metric-value { font-size: 26px; font-weight: 900; line-height: 1.1; margin: 4px 0; }
.metric-desc, .card-title { font-size: 13px; }
.card-title { font-weight: 800; margin-bottom: 6px; }
.flow-line { display: grid; grid-template-columns: repeat(auto-fit, minmax(128px, 1fr)); gap: 10px; }
.flow-step { border: 1px solid rgba(148, 163, 184, .24); border-radius: 12px; padding: 12px; background: rgba(255, 255, 255, .04); }
.step-index { width: 26px; height: 26px; border-radius: 999px; display: grid; place-items: center; font-size: 12px; font-weight: 800; background: rgba(59, 130, 246, .14); margin-bottom: 8px; }
.step-title { font-size: 13px; font-weight: 800; }
.governance-table code { font-size: 11px; white-space: nowrap; }
.ambiente-row { cursor: pointer; transition: background 0.15s ease; }
.ambiente-row:hover { background: rgba(245, 158, 11, 0.08); }
.ambiente-row:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.analytics-flow { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.analytics-node { border: 1px solid rgba(148, 163, 184, .24); border-radius: 999px; padding: 9px 12px; font-size: 13px; font-weight: 800; }
@media (max-width: 700px) { .hero-actions { justify-content: flex-start; } .analytics-node { width: 100%; border-radius: 12px; } }
</style>
