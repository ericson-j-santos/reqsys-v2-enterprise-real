<template>
  <div class="pipeline-page">
    <div class="page-header">
      <div>
        <div class="text-h5 font-weight-bold mb-1">Pipeline</div>
        <div class="text-body-2 text-medium-emphasis">
          Triagem, validação, estruturação e publicação operacional de demandas em um único fluxo.
        </div>
      </div>

      <div class="page-actions">
        <v-chip :color="pipelineStatusColor" variant="tonal">{{ pipelineStatusLabel }}</v-chip>
        <v-btn variant="outlined" prepend-icon="mdi-refresh" :loading="running" @click="resetFlow">
          Limpar
        </v-btn>
        <v-btn color="primary" prepend-icon="mdi-play-circle-outline" :loading="running" @click="runPipeline">
          Executar pipeline
        </v-btn>
      </div>
    </div>

    <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4" closable @click:close="errorMessage = ''">
      {{ errorMessage }}
    </v-alert>

    <v-alert v-if="running" type="info" variant="tonal" class="mb-2" icon="mdi-progress-clock">
      Pipeline em execução. Acompanhe o andamento pelos cards de status.
    </v-alert>

    <v-row>
      <v-col cols="12" lg="5">
        <v-card rounded="xl" elevation="1" class="panel-card h-100">
          <v-card-title>Solicitação de requisito</v-card-title>
          <v-divider />
          <v-card-text>
            <v-form @submit.prevent="runPipeline">
              <v-select v-model="form.origem" :items="origins" label="Origem" variant="outlined" density="comfortable" class="mb-3" />
              <v-text-field v-model="form.titulo" label="Título" variant="outlined" density="comfortable" class="mb-3" />
              <v-textarea v-model="form.descricao" label="Descrição" variant="outlined" density="comfortable" rows="5" class="mb-3" />

              <v-row>
                <v-col cols="12" sm="6">
                  <v-text-field v-model="form.solicitante" label="Solicitante" variant="outlined" density="comfortable" />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-select v-model="form.urgencia" :items="urgencies" label="Urgência" variant="outlined" density="comfortable" />
                </v-col>
              </v-row>

              <v-row>
                <v-col cols="12" sm="6">
                  <v-text-field v-model="form.area" label="Área" variant="outlined" density="comfortable" />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field v-model="form.sistema" label="Sistema" variant="outlined" density="comfortable" />
                </v-col>
              </v-row>

              <v-text-field v-model="form.modulo" label="Módulo" variant="outlined" density="comfortable" class="mb-2" />
              <v-checkbox v-model="form.impacto_regulatorio" label="Impacto regulatório / compliance" color="primary" hide-details class="mb-4" />

              <v-btn block color="primary" size="large" prepend-icon="mdi-send-outline" :loading="running" @click="runPipeline">
                Executar fluxo completo
              </v-btn>
            </v-form>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="7">
        <v-card rounded="xl" elevation="1" class="panel-card mb-4">
          <v-card-title>Status do fluxo</v-card-title>
          <v-divider />
          <v-card-text>
            <div class="steps-grid">
              <div v-for="step in steps" :key="step.key" class="step-card" :class="`step-${step.status}`">
                <div class="step-card__header">
                  <v-icon :color="stepColor(step.status)">{{ stepIcon(step.status) }}</v-icon>
                  <span class="font-weight-medium">{{ step.label }}</span>
                </div>
                <div class="text-caption text-medium-emphasis mt-2">{{ step.detail || 'Aguardando execução.' }}</div>
              </div>
            </div>
          </v-card-text>
        </v-card>

        <v-card rounded="xl" elevation="1" class="panel-card mb-4">
          <v-card-title>Resultado da execução</v-card-title>
          <v-divider />
          <v-card-text>
            <v-row>
              <v-col cols="12" sm="6">
                <div class="result-item">
                  <div class="result-label">Código da solicitação</div>
                  <div class="result-value">{{ requestResult?.codigo || '—' }}</div>
                </div>
              </v-col>
              <v-col cols="12" sm="6">
                <div class="result-item">
                  <div class="result-label">Requisito gerado</div>
                  <div class="result-value">{{ structureResult?.codigo_requisito || '—' }}</div>
                </div>
              </v-col>
              <v-col cols="12" sm="6">
                <div class="result-item">
                  <div class="result-label">Triagem</div>
                  <div class="result-value">{{ validationResult?.aprovado_para_triagem ? 'Aprovada' : 'Com alertas' }}</div>
                </div>
              </v-col>
              <v-col cols="12" sm="6">
                <div class="result-item">
                  <div class="result-label">Backlog</div>
                  <div class="result-value">{{ publishResult?.issue_principal_id || '—' }}</div>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <v-card rounded="xl" elevation="1" class="panel-card">
          <v-card-title>Alertas e subtarefas</v-card-title>
          <v-divider />
          <v-card-text>
            <v-list density="comfortable">
              <v-list-item
                v-for="(warning, index) in allWarnings"
                :key="`warning-${index}`"
                :title="warning"
                prepend-icon="mdi-alert-outline"
              />
              <v-list-item v-if="!allWarnings.length" title="Sem alertas relevantes." />
            </v-list>
            <v-divider class="my-3" />
            <v-list density="comfortable">
              <v-list-item
                v-for="task in publishResult?.subtarefas || []"
                :key="task.id"
                :title="task.subject"
                :subtitle="`ID ${task.id}`"
                prepend-icon="mdi-subdirectory-arrow-right"
              />
              <v-list-item v-if="!(publishResult?.subtarefas || []).length" title="Nenhuma subtarefa gerada." />
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import api from '../services/api'
import { useStatusBanner } from '../composables/useStatusBanner'

const { errorMessage, setError } = useStatusBanner()

const origins = ['Email', 'Reunião', 'Portal', 'Redmine', 'GitHub']
const urgencies = ['baixa', 'media', 'alta', 'critica']

const form = reactive({
  origem: 'Portal',
  titulo: 'Nova demanda operacional para rastreabilidade do fluxo',
  descricao: 'Permitir que a equipe acompanhe o fluxo completo de uma demanda, desde a triagem até a publicação no backlog, com visibilidade operacional e alertas de validação.',
  solicitante: 'Equipe de Produtos',
  area: 'Governança',
  sistema: 'ReqSys',
  modulo: 'Pipeline',
  urgencia: 'media',
  impacto_regulatorio: false,
})

const running = ref(false)
const requestResult = ref(null)
const validationResult = ref(null)
const structureResult = ref(null)
const publishResult = ref(null)

const steps = ref([
  { key: 'solicitacao', label: 'Solicitação', status: 'idle', detail: '' },
  { key: 'validacao', label: 'Validação', status: 'idle', detail: '' },
  { key: 'estruturacao', label: 'Estruturação', status: 'idle', detail: '' },
  { key: 'publicacao', label: 'Publicação', status: 'idle', detail: '' },
])

const allWarnings = computed(() => [
  ...(validationResult.value?.alertas || []),
  ...(publishResult.value?.warnings || []),
])

const pipelineStatusLabel = computed(() => {
  if (running.value) return 'Executando'
  if (publishResult.value?.issue_principal_id) return 'Concluído'
  if (allWarnings.value.length) return 'Com alertas'
  return 'Pronto'
})

const pipelineStatusColor = computed(() => {
  if (running.value) return 'primary'
  if (publishResult.value?.issue_principal_id) return 'success'
  if (allWarnings.value.length) return 'warning'
  return 'grey'
})

function stepColor(status) {
  return {
    idle: 'grey',
    running: 'primary',
    success: 'success',
    warning: 'warning',
    error: 'error',
  }[status] || 'grey'
}

function stepIcon(status) {
  return {
    idle: 'mdi-clock-outline',
    running: 'mdi-progress-clock',
    success: 'mdi-check-circle-outline',
    warning: 'mdi-alert-outline',
    error: 'mdi-close-circle-outline',
  }[status] || 'mdi-clock-outline'
}

function setStep(key, status, detail = '') {
  steps.value = steps.value.map((step) => step.key === key ? { ...step, status, detail } : step)
}

function resetFlow() {
  setError('')
  requestResult.value = null
  validationResult.value = null
  structureResult.value = null
  publishResult.value = null
  steps.value = steps.value.map((step) => ({ ...step, status: 'idle', detail: '' }))
}

async function runPipeline() {
  running.value = true
  resetFlow()

  try {
    setStep('solicitacao', 'running', 'Registrando solicitação inicial.')
    const requestResponse = await api.post('/v1/solicitacoes', form)
    requestResult.value = requestResponse?.data?.data || null
    setStep('solicitacao', 'success', `Solicitação ${requestResult.value?.codigo || 'gerada'}.`)

    setStep('validacao', 'running', 'Validando clareza e critérios de aceite.')
    const validationResponse = await api.post('/v1/requisitos/validar', {
      titulo: form.titulo,
      descricao: form.descricao,
      requisitos_funcionais: [],
      criterios_aceite: [],
    })
    validationResult.value = validationResponse?.data?.data || null
    setStep(
      'validacao',
      validationResult.value?.alertas?.length ? 'warning' : 'success',
      validationResult.value?.alertas?.length ? `${validationResult.value.alertas.length} alerta(s) identificados.` : 'Validação sem alertas.',
    )

    setStep('estruturacao', 'running', 'Estruturando requisito para backlog.')
    const structureResponse = await api.post('/v1/requisitos/estruturar/1', form)
    structureResult.value = structureResponse?.data?.data || null
    setStep('estruturacao', 'success', `Requisito ${structureResult.value?.codigo_requisito || 'estruturado'}.`)

    setStep('publicacao', 'running', 'Publicando backlog e subtarefas.')
    const publishResponse = await api.post('/v1/backlog/publicar-redmine/1', {
      use_github_import: false,
    })
    publishResult.value = publishResponse?.data?.data || null
    setStep('publicacao', publishResult.value?.warnings?.length ? 'warning' : 'success', `Backlog ${publishResult.value?.issue_principal_id || 'publicado'}.`)
  } catch (error) {
    setError(error?.response?.data?.detail || error?.message || 'Erro ao executar pipeline.')
    const runningStep = steps.value.find((step) => step.status === 'running')
    if (runningStep) {
      setStep(runningStep.key, 'error', 'Execução interrompida por erro.')
    }
  } finally {
    running.value = false
  }
}
</script>

<style scoped>
.pipeline-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.page-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.panel-card {
  border: 1px solid rgba(208, 208, 208, 0.9);
}

.steps-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.step-card {
  border: 1px solid rgba(208, 208, 208, 0.9);
  border-radius: 16px;
  padding: 14px;
  background: #f8fbff;
}

.step-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-success {
  border-color: rgba(46, 125, 50, 0.35);
}

.step-warning {
  border-color: rgba(245, 124, 0, 0.35);
}

.step-error {
  border-color: rgba(198, 40, 40, 0.35);
}

.result-item {
  border: 1px solid rgba(208, 208, 208, 0.9);
  border-radius: 16px;
  padding: 14px;
  background: #f8fbff;
  height: 100%;
}

.result-label {
  font-size: 12px;
  color: rgba(51, 51, 51, 0.72);
  margin-bottom: 6px;
}

.result-value {
  font-size: 18px;
  font-weight: 700;
  color: rgb(var(--v-theme-primary));
}

@media (max-width: 600px) {
  .steps-grid {
    grid-template-columns: 1fr;
  }
}
</style>
