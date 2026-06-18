<template>
  <section class="page task-console-page">
    <PageHeader
      title="Task Console"
      subtitle="Operacao ReqSys para revisar tarefas e preparar envio ao Planner."
      chip="Power Apps ready"
      chip-color="teal"
      chip-tooltip="Tela web alinhada ao blueprint do Canvas App ReqSys Task Console."
    >
      <template #actions>
        <v-tooltip text="Copia o texto no formato aceito pelo Flow ReqSys - Criar no Planner" location="top">
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="outlined" prepend-icon="mdi-content-copy" @click="copiarFlowText">
              Copiar Flow
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Baixa as tarefas em CSV compativel com o modelo Power Automate" location="top">
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="outlined" prepend-icon="mdi-file-delimited-outline" @click="baixarCsv">
              CSV
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Envia as tarefas pendentes para o Flow ReqSys - Criar no Planner" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              color="teal"
              prepend-icon="mdi-send-check"
              :loading="envioPlanner"
              :disabled="envioPlanner || tarefasPendentes.length === 0"
              @click="enviarPlanner"
            >
              Enviar Planner
            </v-btn>
          </template>
        </v-tooltip>
      </template>
    </PageHeader>

    <v-alert
      v-if="feedback.msg"
      :type="feedback.type"
      variant="tonal"
      density="compact"
      class="mb-4"
      closable
      @click:close="feedback.msg = ''"
    >
      {{ feedback.msg }}
    </v-alert>

    <v-alert
      v-if="ambienteAtual.url_acesso"
      type="info"
      variant="tonal"
      density="compact"
      class="mb-4"
    >
      Ambiente: <strong>{{ ambienteAtual.ambiente }}</strong> Â· Acesso:
      <a :href="ambienteAtual.url_acesso" target="_blank">{{ ambienteAtual.url_acesso }}</a>
    </v-alert>

    <v-row class="mb-4">
      <v-col v-for="metric in metrics" :key="metric.label" cols="12" sm="6" lg="3">
        <v-card class="metric-card">
          <div class="metric-icon">
            <v-icon size="22">{{ metric.icon }}</v-icon>
          </div>
          <div>
            <div class="muted">{{ metric.label }}</div>
            <div class="metric-value">{{ metric.value }}</div>
          </div>
        </v-card>
      </v-col>
    </v-row>

    <v-row align="start">
      <v-col cols="12" lg="8">
        <v-card class="table-card">
          <v-card-title class="panel-title">
            <span>Tarefas</span>
            <div class="filters">
              <v-select
                v-model="bucketFiltro"
                :items="bucketOptions"
                label="Bucket"
                density="compact"
                variant="outlined"
                hide-details
                clearable
              />
              <v-select
                v-model="prioridadeFiltro"
                :items="priorityOptions"
                label="Prioridade"
                density="compact"
                variant="outlined"
                hide-details
                clearable
              />
            </div>
          </v-card-title>

          <v-data-table
            :headers="headers"
            :items="tarefasFiltradas"
            item-value="id"
            density="comfortable"
            class="task-table"
          >
            <template v-slot:[`item.titulo`]="{ item }">
              <div class="task-title">{{ item.titulo }}</div>
              <div class="muted task-description">{{ item.descricao || 'Sem descricao' }}</div>
            </template>
            <template v-slot:[`item.prioridade`]="{ item }">
              <v-chip size="small" :color="priorityColor(item.prioridade)" variant="tonal">
                {{ item.prioridade }}
              </v-chip>
            </template>
            <template v-slot:[`item.status`]="{ item }">
              <v-chip size="small" :color="statusColor(item.status)" variant="tonal">
                {{ item.status }}
              </v-chip>
            </template>
            <template v-slot:[`item.acoes`]="{ item }">
              <v-tooltip text="Remove a tarefa desta lista local" location="top">
                <template #activator="{ props }">
                  <v-btn
                    v-bind="props"
                    icon="mdi-delete-outline"
                    variant="text"
                    color="error"
                    size="small"
                    @click="removerTarefa(item.id)"
                  />
                </template>
              </v-tooltip>
            </template>
          </v-data-table>
        </v-card>

        <v-card class="table-card mt-4">
          <v-card-title class="panel-title">
            <span>Payload Flow</span>
            <v-chip size="small" color="blue" variant="tonal">tarefas_texto</v-chip>
          </v-card-title>
          <v-card-text>
            <pre class="payload-box">{{ payloadPreview }}</pre>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="4">
        <v-card class="table-card mb-4">
          <v-card-title class="panel-title">
            <span>Nova tarefa</span>
          </v-card-title>
          <v-card-text>
            <v-form ref="formRef" v-model="formValido" @submit.prevent="adicionarTarefa">
              <v-text-field
                v-model="form.titulo"
                label="Titulo"
                variant="outlined"
                density="compact"
                :rules="[rules.required, rules.minTitle]"
                class="mb-2"
              />
              <v-textarea
                v-model="form.descricao"
                label="Descricao"
                variant="outlined"
                density="compact"
                rows="3"
                class="mb-2"
              />
              <v-row dense>
                <v-col cols="12" sm="6">
                  <v-select
                    v-model="form.prioridade"
                    :items="priorityOptions"
                    label="Prioridade"
                    variant="outlined"
                    density="compact"
                    class="mb-2"
                  />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field
                    v-model="form.prazo"
                    type="date"
                    label="Prazo"
                    variant="outlined"
                    density="compact"
                    class="mb-2"
                  />
                </v-col>
              </v-row>
              <v-row dense>
                <v-col cols="12" sm="6">
                  <v-select
                    v-model="form.bucket"
                    :items="bucketOptions"
                    label="Bucket"
                    variant="outlined"
                    density="compact"
                    class="mb-2"
                  />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field
                    v-model="form.responsavelEmail"
                    label="Responsavel"
                    variant="outlined"
                    density="compact"
                    class="mb-2"
                  />
                </v-col>
              </v-row>
              <v-btn type="submit" color="teal" prepend-icon="mdi-plus" block>
                Adicionar
              </v-btn>
            </v-form>
          </v-card-text>
        </v-card>

        <v-card class="table-card mb-4">
          <v-card-title class="panel-title">
            <span>Importacao rapida</span>
          </v-card-title>
          <v-card-text>
            <v-textarea
              v-model="bulkText"
              label="Linhas"
              variant="outlined"
              rows="6"
              density="compact"
              class="mb-2"
            />
            <v-btn variant="outlined" prepend-icon="mdi-import" block @click="importarLinhas">
              Importar linhas
            </v-btn>
          </v-card-text>
        </v-card>

        <v-card class="table-card">
          <v-card-title class="panel-title">
            <span>Resumo por bucket</span>
          </v-card-title>
          <v-card-text>
            <div v-for="bucket in bucketSummary" :key="bucket.nome" class="bucket-row">
              <span>{{ bucket.nome }}</span>
              <div class="bucket-track">
                <div class="bucket-fill" :style="{ width: bucket.percent + '%' }" />
              </div>
              <strong>{{ bucket.total }}</strong>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import { api } from '../services/api'

const STORAGE_KEY = 'reqsys_task_console_tasks'

const priorityOptions = ['Alta', 'Media', 'Baixa']
const bucketOptions = ['Backlog', 'Desenvolvimento', 'Marketing']

const defaultTasks = [
  {
    id: makeId(),
    titulo: 'Gerar Relatorio Mensal',
    descricao: 'Implementar funcionalidade R1',
    prioridade: 'Alta',
    prazo: '2026-06-25',
    bucket: 'Backlog',
    responsavelEmail: '',
    status: 'Pendente',
  },
  {
    id: makeId(),
    titulo: 'Seguranca e Performance',
    descricao: 'Implementar R2',
    prioridade: 'Alta',
    prazo: '2026-06-30',
    bucket: 'Desenvolvimento',
    responsavelEmail: '',
    status: 'Pendente',
  },
  {
    id: makeId(),
    titulo: 'Desconto VIP',
    descricao: 'Implementar regra de negocio R3',
    prioridade: 'Alta',
    prazo: '2026-07-05',
    bucket: 'Marketing',
    responsavelEmail: '',
    status: 'Pendente',
  },
]

const tarefas = ref(loadTasks())
const bucketFiltro = ref('')
const prioridadeFiltro = ref('')
const formRef = ref(null)
const formValido = ref(false)
const envioPlanner = ref(false)
const ultimoEnvioPlanner = ref(null)
const ambienteAtual = ref({ ambiente: '', url_acesso: '', frontend: '', api: '' })

const form = reactive({
  titulo: 'Revisar integracao Planner',
  descricao: 'Validar campos de prazo, bucket, prioridade e responsavel antes de acionar o Flow.',
  prioridade: 'Alta',
  prazo: '2026-06-25',
  bucket: 'Backlog',
  responsavelEmail: '',
})

const bulkText = ref([
  'Gerar Relatorio Mensal | ana@empresa.com | 2026-06-25 | Backlog | Alta | Implementar R1',
  'Seguranca e Performance | bruno@empresa.com | 2026-06-30 | Desenvolvimento | Alta | Implementar R2',
].join('\n'))

const feedback = reactive({ type: 'success', msg: '' })

const rules = {
  required: (value) => Boolean(String(value || '').trim()) || 'Obrigatorio',
  minTitle: (value) => String(value || '').trim().length >= 4 || 'Minimo 4 caracteres',
}

const headers = [
  { title: 'Titulo', key: 'titulo', minWidth: 260 },
  { title: 'Bucket', key: 'bucket', width: 150 },
  { title: 'Prioridade', key: 'prioridade', width: 130 },
  { title: 'Prazo', key: 'prazo', width: 130 },
  { title: 'Status', key: 'status', width: 130 },
  { title: '', key: 'acoes', width: 72, sortable: false },
]

const tarefasFiltradas = computed(() => tarefas.value.filter((tarefa) => {
  const bucketOk = !bucketFiltro.value || tarefa.bucket === bucketFiltro.value
  const prioridadeOk = !prioridadeFiltro.value || tarefa.prioridade === prioridadeFiltro.value
  return bucketOk && prioridadeOk
}))

const tarefasPendentes = computed(() => tarefas.value.filter((tarefa) => tarefa.status === 'Pendente'))

const metrics = computed(() => [
  {
    label: 'Pendentes',
    value: tarefas.value.filter((t) => t.status === 'Pendente').length,
    icon: 'mdi-progress-clock',
  },
  {
    label: 'Criadas',
    value: tarefas.value.filter((t) => t.status === 'Criada').length,
    icon: 'mdi-check-circle-outline',
  },
  {
    label: 'Alta prioridade',
    value: tarefas.value.filter((t) => t.prioridade === 'Alta').length,
    icon: 'mdi-alert-circle-outline',
  },
  {
    label: 'Buckets',
    value: new Set(tarefas.value.map((t) => t.bucket)).size,
    icon: 'mdi-view-column-outline',
  },
])

const flowText = computed(() => tarefas.value
  .filter((tarefa) => tarefa.status === 'Pendente')
  .map((tarefa) => [
    tarefa.titulo,
    tarefa.responsavelEmail,
    tarefa.prazo,
    tarefa.bucket,
    tarefa.prioridade,
    tarefa.descricao,
  ].join(' | '))
  .join('\n'))

const payloadPreview = computed(() => JSON.stringify({
  flow: 'ReqSys - Criar no Planner',
  endpoint: '/v1/hub-lowcode/planner/tasks',
  input: {
    tarefas_texto: flowText.value,
    autor: 'Usuario ReqSys',
  },
  tarefas: tarefasPendentes.value.map(toPlannerPayload),
  ultimo_envio: ultimoEnvioPlanner.value,
}, null, 2))

const bucketSummary = computed(() => {
  const max = Math.max(1, ...bucketOptions.map((bucket) => tarefas.value.filter((t) => t.bucket === bucket).length))
  return bucketOptions.map((bucket) => {
    const total = tarefas.value.filter((tarefa) => tarefa.bucket === bucket).length
    return {
      nome: bucket,
      total,
      percent: Math.max(6, Math.round((total / max) * 100)),
    }
  })
})

watch(tarefas, (value) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
}, { deep: true })

async function adicionarTarefa() {
  const validation = await formRef.value?.validate()
  if (!validation?.valid) return

  tarefas.value.push({
    id: makeId(),
    titulo: form.titulo.trim(),
    descricao: form.descricao.trim(),
    prioridade: form.prioridade,
    prazo: form.prazo,
    bucket: form.bucket,
    responsavelEmail: form.responsavelEmail.trim(),
    status: 'Pendente',
  })
  feedbackOk('Tarefa adicionada.')
}

function importarLinhas() {
  const novas = bulkText.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split('|').map((part) => part.trim())
      return {
        id: makeId(),
        titulo: parts[0] || 'Tarefa sem titulo',
        responsavelEmail: parts[1] || '',
        prazo: parts[2] || '',
        bucket: bucketOptions.includes(parts[3]) ? parts[3] : 'Backlog',
        prioridade: priorityOptions.includes(parts[4]) ? parts[4] : 'Media',
        descricao: parts[5] || '',
        status: 'Pendente',
      }
    })

  tarefas.value.push(...novas)
  feedbackOk(`${novas.length} tarefa(s) importada(s).`)
}

async function enviarPlanner() {
  if (tarefasPendentes.value.length === 0) {
    feedbackWarn('Nao ha tarefas pendentes para enviar ao Planner.')
    return
  }

  envioPlanner.value = true
  ultimoEnvioPlanner.value = null

  try {
    const pendentes = tarefasPendentes.value.map(toPlannerPayload)
    const { data } = await api.post('/v1/hub-lowcode/planner/tasks', {
      tarefas: pendentes,
      autor: 'Usuario ReqSys',
    })
    const resultado = data.data
    ultimoEnvioPlanner.value = {
      configurado: resultado.configurado,
      enviado: resultado.enviado,
      total: resultado.total,
      flow: resultado.flow,
      flow_id: resultado.flow_id,
      correlation_id: resultado.correlation_id,
      resposta_flow: resultado.resposta_flow,
      ambiente: resultado.ambiente,
    }
    if (resultado.ambiente) ambienteAtual.value = resultado.ambiente

    if (!resultado.enviado) {
      feedbackWarn(formatarFalhaPlanner(resultado))
      return
    }

    const enviados = new Set(pendentes.map((tarefa) => tarefa.id))
    tarefas.value = tarefas.value.map((tarefa) => {
      if (!enviados.has(tarefa.id)) return tarefa
      return {
        ...tarefa,
        status: 'Criada',
        plannerFlowId: resultado.flow_id,
        plannerCorrelationId: resultado.correlation_id,
        plannerEnviadoEm: new Date().toISOString(),
      }
    })
    feedbackOk(resultado.mensagem || `${pendentes.length} tarefa(s) enviada(s) ao Planner.`)
  } catch (error) {
    const msg = error.response?.data?.detail || error.message || 'Falha ao enviar tarefas ao Planner.'
    feedbackErro(msg)
  } finally {
    envioPlanner.value = false
  }
}

async function carregarAmbienteAtual() {
  try {
    const { data } = await api.get('/v1/hub-lowcode/status')
    const payload = data.data ?? data
    if (payload.ambiente) ambienteAtual.value = payload.ambiente
  } catch {}
}

function removerTarefa(id) {
  tarefas.value = tarefas.value.filter((tarefa) => tarefa.id !== id)
}

async function copiarFlowText() {
  try {
    await navigator.clipboard.writeText(flowText.value)
    feedbackOk('Texto do Flow copiado.')
  } catch {
    feedbackWarn('Nao foi possivel copiar automaticamente.')
  }
}

function baixarCsv() {
  const header = 'Titulo,Descricao,Prioridade,Prazo,Bucket,ResponsavelEmail'
  const rows = tarefas.value.map((tarefa) => [
    tarefa.titulo,
    tarefa.descricao,
    tarefa.prioridade,
    tarefa.prazo,
    tarefa.bucket,
    tarefa.responsavelEmail,
  ].map(csvCell).join(','))
  const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'reqsys-planner-tasks.csv'
  link.click()
  URL.revokeObjectURL(url)
}

function priorityColor(priority) {
  return { Alta: 'red', Media: 'amber', Baixa: 'blue' }[priority] || 'grey'
}

function statusColor(status) {
  return { Pendente: 'orange', Criada: 'green', Falha: 'red' }[status] || 'grey'
}

function feedbackOk(msg) {
  feedback.type = 'success'
  feedback.msg = msg
}

function feedbackWarn(msg) {
  feedback.type = 'warning'
  feedback.msg = msg
}

function feedbackErro(msg) {
  feedback.type = 'error'
  feedback.msg = msg
}

function formatarFalhaPlanner(resultado) {
  const partes = [resultado.mensagem || 'Flow Planner nao configurado; nenhuma tarefa foi marcada como criada.']
  const resposta = resultado.resposta_flow || {}
  if (resposta.status_code) partes.push(`Status Power Automate: ${resposta.status_code}.`)
  if (resposta.body) partes.push(`Detalhe: ${String(resposta.body).slice(0, 260)}`)
  return partes.join(' ')
}

function toPlannerPayload(tarefa) {
  return {
    id: tarefa.id,
    titulo: tarefa.titulo,
    descricao: tarefa.descricao || '',
    prioridade: tarefa.prioridade || 'Media',
    prazo: tarefa.prazo || '',
    bucket: tarefa.bucket || 'Backlog',
    responsavelEmail: tarefa.responsavelEmail || '',
  }
}

function csvCell(value) {
  return `"${String(value || '').replaceAll('"', '""')}"`
}

function makeId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `task-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function loadTasks() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    if (Array.isArray(saved) && saved.length) return saved
  } catch {}
  return defaultTasks
}

onMounted(carregarAmbienteAtual)
</script>

<style scoped>
.task-console-page {
  max-width: 1480px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  min-height: 96px;
}

.metric-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  color: #004d45;
  background: #d7f7ef;
}

.metric-value {
  margin-top: 4px;
  font-size: 28px;
  color: var(--accent-strong);
  font-weight: 800;
}

.panel-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 15px;
  font-weight: 700;
}

.filters {
  display: grid;
  grid-template-columns: 180px 170px;
  gap: 8px;
}

.task-title {
  font-weight: 700;
  color: var(--text);
}

.task-description {
  margin-top: 2px;
  max-width: 64ch;
}

.payload-box {
  margin: 0;
  min-height: 220px;
  max-height: 340px;
  overflow: auto;
  white-space: pre-wrap;
  color: #dbeafe;
  background: #102033;
  border: 1px solid #24425f;
  border-radius: 8px;
  padding: 14px;
  font: 12px/1.5 Consolas, 'Courier New', monospace;
}

.bucket-row {
  display: grid;
  grid-template-columns: 132px minmax(80px, 1fr) 32px;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 13px;
}

.bucket-track {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: #e8f1fa;
}

.bucket-fill {
  height: 100%;
  min-width: 4px;
  background: var(--accent-tertiary);
}

:deep(.task-table .v-data-table__td) {
  vertical-align: top;
}

@media (max-width: 780px) {
  .filters {
    width: 100%;
    grid-template-columns: 1fr;
  }
}
</style>
