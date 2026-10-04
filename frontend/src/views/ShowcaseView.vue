<template>
  <main class="showcase-page" data-testid="reqsys-showcase">
    <header class="showcase-header">
      <div class="brand-lockup">
        <div class="brand-mark">R</div>
        <div>
          <strong>ReqSys</strong>
          <span>Demonstração v1</span>
        </div>
      </div>
      <div class="header-actions">
        <v-chip color="amber" variant="flat" prepend-icon="mdi-flask-outline" data-testid="demo-banner">
          AMBIENTE DE DEMONSTRAÇÃO · DADOS FICTÍCIOS
        </v-chip>
        <v-btn variant="text" href="/login" append-icon="mdi-arrow-right">Acessar ReqSys</v-btn>
      </div>
    </header>

    <section class="hero-panel">
      <div class="hero-copy">
        <div class="eyebrow">Do problema à evidência</div>
        <h1>Veja uma demanda virar execução governada, rastreável e resiliente.</h1>
        <p>
          Esta experiência é isolada do ambiente operacional. Nenhuma credencial, dado real ou integração produtiva é utilizada.
        </p>
        <div class="hero-badges">
          <v-chip size="small" variant="tonal" color="green" prepend-icon="mdi-shield-check-outline">sem dado sensível</v-chip>
          <v-chip size="small" variant="tonal" color="blue" prepend-icon="mdi-database-off-outline">sem persistência real</v-chip>
          <v-chip size="small" variant="tonal" color="purple" prepend-icon="mdi-api-off">integrações simuladas</v-chip>
        </div>
      </div>

      <v-card class="audience-card" variant="tonal">
        <div class="eyebrow">Profundidade da apresentação</div>
        <v-btn-toggle v-model="audience" mandatory density="comfortable" class="audience-toggle" data-testid="audience-toggle">
          <v-btn value="executivo">Executivo</v-btn>
          <v-btn value="negocio">Negócio / PO</v-btn>
          <v-btn value="tecnico">Técnico</v-btn>
        </v-btn-toggle>
        <p class="mb-0">{{ audienceCopy }}</p>
      </v-card>
    </section>

    <section class="metrics-grid" aria-label="Indicadores fictícios da demonstração">
      <v-card v-for="metric in demoMetrics" :key="metric.label" class="metric-card" variant="flat">
        <div class="metric-value">{{ metric.value }}</div>
        <div class="metric-label">{{ metric.label }}</div>
        <small>{{ metric.detail }}</small>
      </v-card>
    </section>

    <section class="section-block">
      <div class="section-heading">
        <div>
          <div class="eyebrow">Escolha uma história</div>
          <h2>Cinco cenários para demonstrar o ReqSys</h2>
        </div>
        <v-chip color="blue" variant="tonal">5 cenários versionados</v-chip>
      </div>

      <div class="scenario-grid" data-testid="scenario-grid">
        <button
          v-for="scenario in scenarios"
          :key="scenario.id"
          type="button"
          class="scenario-card"
          :class="{ 'scenario-card--active': scenario.id === selectedScenarioId }"
          :data-testid="`scenario-${scenario.id}`"
          @click="selectScenario(scenario.id)"
        >
          <v-icon :icon="scenario.icon" size="24" :color="scenario.color" />
          <div>
            <strong>{{ scenario.title }}</strong>
            <span>{{ scenario.short }}</span>
          </div>
          <v-chip size="x-small" :color="scenario.color" variant="tonal">{{ scenario.tag }}</v-chip>
        </button>
      </div>
    </section>

    <section class="demo-stage" data-testid="demo-stage">
      <div class="demo-stage__header">
        <div>
          <div class="eyebrow">Cenário em execução</div>
          <h2>{{ selectedScenario.title }}</h2>
          <p>{{ selectedScenario.description }}</p>
        </div>
        <div class="stage-status">
          <v-chip :color="progress === 100 ? 'green' : 'amber'" variant="tonal" data-testid="demo-status">
            {{ currentState }}
          </v-chip>
          <strong>{{ progress }}%</strong>
        </div>
      </div>

      <v-progress-linear :model-value="progress" height="8" rounded color="amber" />

      <div class="flow-strip" aria-label="Fluxo canônico do ReqSys">
        <div v-for="(step, index) in selectedScenario.steps" :key="step.id" class="flow-step" :class="stepClass(index)">
          <div class="flow-index">
            <v-icon v-if="index <= completedStepIndex" icon="mdi-check" size="16" />
            <span v-else>{{ index + 1 }}</span>
          </div>
          <div>
            <strong>{{ step.title }}</strong>
            <small>{{ step.detail }}</small>
          </div>
        </div>
      </div>

      <div class="demo-actions">
        <v-btn color="amber" variant="flat" prepend-icon="mdi-play" :disabled="progress === 100" @click="advance">
          Executar próxima etapa
        </v-btn>
        <v-btn variant="tonal" prepend-icon="mdi-fast-forward" :disabled="progress === 100" data-testid="run-all" @click="runAll">
          Executar cenário completo
        </v-btn>
        <v-btn variant="text" prepend-icon="mdi-refresh" @click="resetScenario">Reiniciar</v-btn>
      </div>

      <v-row class="mt-2">
        <v-col cols="12" lg="7">
          <v-card class="evidence-card" variant="tonal" data-testid="evidence-card">
            <v-card-title>Evidências geradas</v-card-title>
            <v-card-subtitle>correlation_id: {{ correlationId }}</v-card-subtitle>
            <v-card-text>
              <div v-if="visibleEvidence.length" class="evidence-list">
                <div v-for="item in visibleEvidence" :key="item.label" class="evidence-item">
                  <v-icon icon="mdi-check-decagram-outline" color="green" size="20" />
                  <div>
                    <strong>{{ item.label }}</strong>
                    <span>{{ item.value }}</span>
                  </div>
                </div>
              </div>
              <v-alert v-else type="info" variant="tonal" density="compact">
                Execute uma etapa para gerar evidências da demonstração.
              </v-alert>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" lg="5">
          <v-card class="outcome-card" variant="flat">
            <v-card-title>O que esta história prova</v-card-title>
            <v-card-text>
              <ul>
                <li v-for="proof in selectedScenario.proofs" :key="proof">{{ proof }}</li>
              </ul>
              <v-alert v-if="progress === 100" :type="selectedScenario.resultType" variant="tonal" density="compact" class="mt-4" data-testid="scenario-result">
                {{ selectedScenario.result }}
              </v-alert>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </section>

    <section v-if="audience !== 'executivo'" class="section-block">
      <div class="section-heading">
        <div>
          <div class="eyebrow">Por trás da jornada</div>
          <h2>Produtor–consumidor e isolamento de falhas</h2>
        </div>
      </div>
      <div class="architecture-grid">
        <v-card v-for="item in architecture" :key="item.title" class="architecture-card" variant="tonal">
          <v-icon :icon="item.icon" size="24" />
          <strong>{{ item.title }}</strong>
          <span>{{ item.description }}</span>
        </v-card>
      </div>
    </section>

    <section v-if="audience === 'tecnico'" class="technical-panel" data-testid="technical-panel">
      <div>
        <div class="eyebrow">Detalhe técnico</div>
        <h2>Controles que permanecem ativos no desenho real</h2>
      </div>
      <div class="technical-chips">
        <v-chip v-for="control in technicalControls" :key="control" size="small" variant="tonal" color="blue">{{ control }}</v-chip>
      </div>
      <p>
        No demonstração os efeitos são simulados. Em execução real, os mesmos conceitos devem ser sustentados por fila/buffer,
        backpressure, idempotência, retentativas controladas, DLQ/quarentena, observabilidade e autorização por ambiente.
      </p>
    </section>

    <footer class="showcase-footer">
      <span>ReqSys Demonstração v1 · ambiente isolado · dados sintéticos</span>
      <span>Nenhuma ação desta tela altera desenvolvimento, homologação ou produção.</span>
    </footer>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'

const audience = ref('executivo')
const selectedScenarioId = ref('happy')
const completedStepIndex = ref(-1)

const audienceCopyByMode = {
  executivo: 'Foco em problema, resultado, risco reduzido e indicadores. Detalhes de implementação ficam ocultos.',
  negocio: 'Foco na jornada da demanda, regras, exceções, aprovação humana e evidências de decisão.',
  tecnico: 'Expõe também resiliência, idempotência, fila, backpressure, DLQ, correlation_id e observabilidade.',
}

const audienceCopy = computed(() => audienceCopyByMode[audience.value])

const demoMetrics = [
  { value: '128', label: 'demandas recebidas', detail: 'amostra sintética' },
  { value: '114', label: 'concluídas', detail: '89,1% do volume' },
  { value: '96,7%', label: 'sucesso técnico', detail: 'cenário demonstrativo' },
  { value: '83%', label: 'automação', detail: 'demais passos governados' },
]

const scenarios = [
  {
    id: 'happy',
    title: 'Happy Path',
    short: 'Demanda válida do início à evidência.',
    tag: 'sucesso',
    icon: 'mdi-check-circle-outline',
    color: 'green',
    description: 'Uma demanda sintética entra completa, passa pelas regras, é enfileirada, processada e concluída com rastreabilidade integral.',
    steps: [
      { id: 'entrada', title: 'Entrada', detail: 'payload sintético recebido' },
      { id: 'validacao', title: 'Validação', detail: 'contrato e regras aprovados' },
      { id: 'fila', title: 'Fila', detail: 'item reservado de forma idempotente' },
      { id: 'processamento', title: 'Processamento', detail: 'worker executa a demanda' },
      { id: 'evidencia', title: 'Evidência', detail: 'resultado e trilha consolidados' },
    ],
    evidence: [
      { label: 'Contrato de entrada', value: 'schema válido · versão demo-1' },
      { label: 'Validação funcional', value: '0 bloqueios · 0 inconsistências' },
      { label: 'Idempotency-Key', value: 'demo-happy-0001' },
      { label: 'Execução do worker', value: 'sucesso · tentativa 1/3' },
      { label: 'Trilha de auditoria', value: 'entrada → decisão → saída registrada' },
    ],
    proofs: ['A demanda não depende de navegação técnica.', 'Cada etapa produz evidência verificável.', 'O processamento é desacoplado da entrada.'],
    resultType: 'success',
    result: 'Demanda concluída sem intervenção humana e com trilha completa.',
  },
  {
    id: 'validation',
    title: 'Validação bloqueia dado incorreto',
    short: 'Erro é detectado antes do processamento.',
    tag: 'fail-fast',
    icon: 'mdi-shield-alert-outline',
    color: 'red',
    description: 'Um campo obrigatório chega inconsistente. O ReqSys interrompe o fluxo antes de consumir recursos downstream e registra a causa objetiva.',
    steps: [
      { id: 'entrada', title: 'Entrada', detail: 'payload sintético recebido' },
      { id: 'validacao', title: 'Validação', detail: 'regra obrigatória falha' },
      { id: 'bloqueio', title: 'Bloqueio', detail: 'fail-closed antes da fila' },
      { id: 'orientacao', title: 'Orientação', detail: 'correção necessária explicitada' },
      { id: 'evidencia', title: 'Evidência', detail: 'falha funcional auditada' },
    ],
    evidence: [
      { label: 'Contrato de entrada', value: 'estrutura válida' },
      { label: 'Regra REQ-DEMO-07', value: 'campo justificativa obrigatório' },
      { label: 'Verificação obrigatória funcional', value: 'bloqueado · sem publicação na fila' },
      { label: 'Próxima ação', value: 'completar justificativa e reenviar' },
      { label: 'Trilha de auditoria', value: 'causa e decisão preservadas' },
    ],
    proofs: ['Erros baratos são capturados cedo.', 'Nenhum worker processa entrada inválida.', 'A correção necessária fica explícita para o usuário.'],
    resultType: 'warning',
    result: 'Demanda bloqueada de forma segura antes do processamento.',
  },
  {
    id: 'ocr',
    title: 'IA / OCR com revisão governada',
    short: 'Documento vira dado estruturado e evidência.',
    tag: 'IA/OCR',
    icon: 'mdi-text-recognition',
    color: 'purple',
    description: 'Um documento fictício é classificado, passa por OCR, validação de confiança e revisão quando necessário antes da persistência lógica.',
    steps: [
      { id: 'documento', title: 'Documento', detail: 'PDF sintético recebido' },
      { id: 'ocr', title: 'OCR', detail: 'campos extraídos com confiança' },
      { id: 'validacao', title: 'Validação', detail: 'regras e nota avaliados' },
      { id: 'revisao', title: 'Revisão', detail: 'campo limítrofe confirmado' },
      { id: 'evidencia', title: 'Evidência', detail: 'resultado estruturado auditado' },
    ],
    evidence: [
      { label: 'Documento', value: 'documento-demo-001.pdf · sintético' },
      { label: 'OCR', value: 'Exact Match 94% · CER demonstrativo 1,8%' },
      { label: 'Confidence verificação obrigatória', value: '1 campo encaminhado à revisão' },
      { label: 'Revisão humana', value: 'campo confirmado · sem dado real' },
      { label: 'Saída estruturada', value: 'JSON validado e rastreável' },
    ],
    proofs: ['IA não decide silenciosamente em baixa confiança.', 'Extração e revisão ficam rastreáveis.', 'O dado demonstrado é inteiramente sintético.'],
    resultType: 'success',
    result: 'Documento convertido em informação estruturada com revisão governada.',
  },
  {
    id: 'outage',
    title: 'Integração externa indisponível',
    short: 'Retry controlado, isolamento e quarentena.',
    tag: 'resiliência',
    icon: 'mdi-cloud-alert-outline',
    color: 'orange',
    description: 'A integração simulada falha. A demanda permanece protegida, recebe retentativas controladas e termina em quarentena sem contaminar o restante do fluxo.',
    steps: [
      { id: 'fila', title: 'Fila', detail: 'demanda preservada no buffer' },
      { id: 'falha', title: 'Falha externa', detail: 'serviço simulada retorna indisponibilidade' },
      { id: 'retry', title: 'Retry', detail: 'retentativas com backoff controlado' },
      { id: 'isolamento', title: 'Isolamento', detail: 'circuit breaker evita efeito cascata' },
      { id: 'dlq', title: 'DLQ', detail: 'item vai para quarentena auditável' },
    ],
    evidence: [
      { label: 'Backlog', value: 'demanda preservada · sem perda' },
      { label: 'Falha externa', value: 'HTTP 503 simulado' },
      { label: 'Retentativas', value: '3/3 · backoff aplicado' },
      { label: 'Circuit breaker', value: 'aberto para origem simulada' },
      { label: 'Quarentena / DLQ', value: 'item isolado com causa e correlation_id' },
    ],
    proofs: ['Falha externa não perde a demanda.', 'Retentativas não são infinitas.', 'Itens problemáticos são isolados para tratamento seguro.'],
    resultType: 'warning',
    result: 'Demanda preservada em quarentena; restante do sistema continua operando.',
  },
  {
    id: 'human',
    title: 'Ação humana governada',
    short: 'O fluxo espera uma decisão que não pode inferir.',
    tag: 'aprovação',
    icon: 'mdi-account-check-outline',
    color: 'blue',
    description: 'Uma decisão sensível exige participação humana explícita. O ReqSys prepara contexto, diff e evidências, mas não infere nem falsifica a aprovação.',
    steps: [
      { id: 'solicitacao', title: 'Solicitação', detail: 'mudança sensível identificada' },
      { id: 'contexto', title: 'Contexto', detail: 'impacto e evidências preparados' },
      { id: 'espera', title: 'Espera segura', detail: 'estado aguardando aprovação' },
      { id: 'aprovacao', title: 'Aprovação', detail: 'decisão humana simulada registrada' },
      { id: 'aplicacao', title: 'Aplicação', detail: 'execução liberada e auditada' },
    ],
    evidence: [
      { label: 'Classificação', value: 'ação sensível · aprovação obrigatória' },
      { label: 'Diff de decisão', value: 'antes/depois apresentado ao aprovador' },
      { label: 'Verificação obrigatória humano', value: 'aguardando decisão explícita' },
      { label: 'Aprovação demo', value: 'ator fictício · timestamp sintético' },
      { label: 'Aplicação', value: 'execução liberada após o verificação obrigatória' },
    ],
    proofs: ['O sistema não inventa pertencimento ou autorização.', 'A decisão humana ocorre no ponto de maior valor.', 'Antes e depois permanecem auditáveis.'],
    resultType: 'success',
    result: 'Ação executada somente após aprovação explícita e rastreável.',
  },
]

const architecture = [
  { icon: 'mdi-inbox-arrow-down-outline', title: 'Produtor', description: 'Entrada desacoplada valida e publica trabalho sem depender do tempo do consumidor.' },
  { icon: 'mdi-tray-full', title: 'Fila / buffer', description: 'Absorve picos, preserva a demanda e permite aplicar backpressure.' },
  { icon: 'mdi-cog-sync-outline', title: 'Consumidor', description: 'Workers processam com concorrência governada, idempotência e isolamento.' },
  { icon: 'mdi-reload-alert', title: 'Retry + DLQ', description: 'Retentativas são limitadas; falha persistente segue para quarentena.' },
  { icon: 'mdi-chart-timeline-variant', title: 'Observabilidade', description: 'Backlog, latência, erros e correlation_id sustentam diagnóstico e evidência.' },
]

const technicalControls = [
  'backpressure',
  'idempotência',
  'retry controlado',
  'circuit breaker',
  'DLQ / quarentena',
  'correlation_id',
  'logs estruturados',
  'métricas de backlog',
  'LGPD / mascaramento',
  'fail-closed',
]

const selectedScenario = computed(() => scenarios.find((item) => item.id === selectedScenarioId.value) || scenarios[0])
const progress = computed(() => Math.round(((completedStepIndex.value + 1) / selectedScenario.value.steps.length) * 100))
const currentState = computed(() => {
  if (completedStepIndex.value < 0) return 'Pronto para iniciar'
  if (completedStepIndex.value >= selectedScenario.value.steps.length - 1) return 'Cenário concluído'
  return `Executado: ${selectedScenario.value.steps[completedStepIndex.value].title}`
})
const correlationId = computed(() => `demo-${selectedScenario.value.id}-reqsys-0001`)
const visibleEvidence = computed(() => selectedScenario.value.evidence.slice(0, completedStepIndex.value + 1))

function selectScenario(id) {
  selectedScenarioId.value = id
  resetScenario()
}

function advance() {
  if (completedStepIndex.value < selectedScenario.value.steps.length - 1) completedStepIndex.value += 1
}

function runAll() {
  completedStepIndex.value = selectedScenario.value.steps.length - 1
}

function resetScenario() {
  completedStepIndex.value = -1
}

function stepClass(index) {
  return {
    'flow-step--complete': index <= completedStepIndex.value,
    'flow-step--current': index === completedStepIndex.value + 1,
  }
}
</script>

<style scoped>
.showcase-page {
  min-height: 100vh;
  padding: var(--space-xl) clamp(18px, 4vw, 64px) var(--space-2xl);
  background:
    radial-gradient(circle at 15% 5%, rgba(255, 193, 7, 0.12), transparent 28%),
    radial-gradient(circle at 90% 20%, rgba(33, 150, 243, 0.1), transparent 30%),
    rgb(var(--v-theme-background));
  color: rgb(var(--v-theme-on-background));
}

.showcase-header,
.hero-panel,
.demo-stage__header,
.section-heading,
.showcase-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.showcase-header {
  max-width: 1440px;
  margin: 0 auto var(--space-2xl);
}

.brand-lockup,
.header-actions,
.hero-badges,
.demo-actions,
.technical-chips {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.brand-lockup > div:last-child {
  display: grid;
}

.brand-lockup span,
.metric-card small,
.flow-step small,
.scenario-card span,
.architecture-card span,
.evidence-item span {
  color: rgba(var(--v-theme-on-surface), 0.68);
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: rgb(var(--v-theme-warning));
  color: #17120a;
  font-weight: 900;
  font-size: var(--font-size-xl);
}

.hero-panel,
.demo-stage,
.technical-panel {
  max-width: 1440px;
  margin: 0 auto;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 24px;
}

.hero-panel {
  align-items: stretch;
  padding: clamp(24px, 4vw, 52px);
  background: rgba(var(--v-theme-surface), 0.74);
  backdrop-filter: blur(12px);
}

.hero-copy {
  max-width: 780px;
}

.hero-copy h1 {
  margin: var(--space-sm) 0 var(--space-lg);
  font-size: clamp(34px, 5vw, 68px);
  line-height: 1.02;
  letter-spacing: -0.045em;
}

.hero-copy p,
.demo-stage__header p,
.technical-panel p {
  color: rgba(var(--v-theme-on-surface), 0.72);
  font-size: 1.05rem;
  line-height: 1.65;
}

.eyebrow {
  color: rgb(var(--v-theme-warning));
  text-transform: uppercase;
  font-size: 0.76rem;
  font-weight: 800;
  letter-spacing: 0.14em;
}

.audience-card {
  width: min(100%, 410px);
  padding: var(--space-xl);
  align-self: center;
}

.audience-toggle {
  margin: var(--space-lg) 0 var(--space-lg);
  flex-wrap: wrap;
}

.metrics-grid,
.scenario-grid,
.architecture-grid {
  max-width: 1440px;
  margin-left: auto;
  margin-right: auto;
  display: grid;
  gap: 14px;
}

.metrics-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: var(--space-lg);
}

.metric-card {
  padding: var(--space-xl);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.metric-value {
  font-size: 1.8rem;
  font-weight: 850;
}

.metric-label {
  font-weight: 700;
  margin-bottom: var(--space-xs);
}

.section-block {
  max-width: 1440px;
  margin: var(--space-3xl) auto 0;
}

.section-heading {
  margin-bottom: var(--space-lg);
}

.section-heading h2,
.demo-stage h2,
.technical-panel h2 {
  margin: var(--space-xs) 0 0;
  font-size: clamp(24px, 3vw, 36px);
}

.scenario-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.scenario-card {
  min-height: 164px;
  padding: var(--space-lg);
  border-radius: 18px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgba(var(--v-theme-surface), 0.72);
  color: inherit;
  text-align: left;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  cursor: pointer;
  transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
}

.scenario-card:hover,
.scenario-card:focus-visible {
  transform: translateY(-2px);
  border-color: rgba(var(--v-theme-warning), 0.8);
  outline: none;
}

.scenario-card--active {
  background: rgba(var(--v-theme-warning), 0.09);
  border-color: rgba(var(--v-theme-warning), 0.85);
}

.scenario-card > div {
  display: grid;
  gap: 5px;
}

.demo-stage {
  margin-top: var(--space-xl);
  padding: clamp(20px, 3vw, 36px);
  background: rgba(var(--v-theme-surface), 0.88);
}

.demo-stage__header {
  align-items: flex-start;
  margin-bottom: var(--space-lg);
}

.demo-stage__header p {
  max-width: 900px;
  margin: var(--space-sm) 0 0;
}

.stage-status {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}

.flow-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin: var(--space-2xl) 0;
}

.flow-step {
  min-height: 116px;
  padding: var(--space-lg);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 16px;
  opacity: 0.58;
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.flow-step > div:last-child {
  display: grid;
  gap: 5px;
}

.flow-index {
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: rgba(var(--v-theme-on-surface), 0.1);
  font-weight: 800;
}

.flow-step--current {
  opacity: 1;
  border-color: rgba(var(--v-theme-warning), 0.8);
}

.flow-step--complete {
  opacity: 1;
  border-color: rgba(var(--v-theme-success), 0.62);
  background: rgba(var(--v-theme-success), 0.06);
}

.flow-step--complete .flow-index {
  background: rgb(var(--v-theme-success));
  color: rgb(var(--v-theme-on-success));
}

.evidence-card,
.outcome-card {
  height: 100%;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.evidence-list {
  display: grid;
  gap: 10px;
}

.evidence-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: var(--space-md) 0;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.18);
}

.evidence-item > div {
  display: grid;
}

.outcome-card ul {
  padding-left: var(--space-xl);
  display: grid;
  gap: 10px;
  color: rgba(var(--v-theme-on-surface), 0.78);
}

.architecture-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.architecture-card {
  padding: var(--space-xl);
  min-height: 176px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.technical-panel {
  margin-top: var(--space-xl);
  padding: clamp(22px, 3vw, 34px);
  background: rgba(var(--v-theme-info), 0.06);
}

.technical-chips {
  margin: var(--space-xl) 0;
}

.showcase-footer {
  max-width: 1440px;
  margin: var(--space-2xl) auto 0;
  padding-top: var(--space-xl);
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.85rem;
}

@media (max-width: 1100px) {
  .hero-panel,
  .showcase-header,
  .demo-stage__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .audience-card {
    width: 100%;
  }

  .scenario-grid,
  .architecture-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .flow-strip {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .showcase-page {
    padding: var(--space-lg) var(--space-lg) var(--space-2xl);
  }

  .header-actions,
  .showcase-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .metrics-grid,
  .scenario-grid,
  .architecture-grid {
    grid-template-columns: 1fr;
  }

  .stage-status {
    white-space: normal;
  }
}
</style>
