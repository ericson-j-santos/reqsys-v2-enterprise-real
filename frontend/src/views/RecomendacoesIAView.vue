<template>
  <div class="ai-rec-page" data-testid="route-recomendacoes-ia">
    <div class="page-header">
      <div>
        <h1>Recomendações IA</h1>
        <p>Recomendações operacionais geradas a partir dos requisitos reais do ReqSys.</p>
      </div>
      <div class="page-actions">
        <v-btn-toggle v-model="windowDays" density="compact" variant="outlined" divided mandatory>
          <v-btn :value="7" size="small">7d</v-btn>
          <v-btn :value="30" size="small">30d</v-btn>
          <v-btn :value="90" size="small">90d</v-btn>
        </v-btn-toggle>
        <v-btn color="primary" prepend-icon="mdi-refresh" :loading="loading" @click="loadAll">Atualizar</v-btn>
      </div>
    </div>

    <v-alert v-if="errorMessage" type="error" variant="tonal" closable @click:close="errorMessage = ''">
      {{ errorMessage }}
    </v-alert>

    <v-row>
      <v-col v-for="card in metricCards" :key="card.title" cols="12" md="4">
        <v-card class="panel-card h-100">
          <v-card-text>
            <div class="text-body-2 text-medium-emphasis">{{ card.title }}</div>
            <div class="text-h4 font-weight-bold mt-1">{{ card.value }}</div>
            <div class="text-caption text-medium-emphasis mt-1">{{ card.subtitle }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12" lg="7">
        <v-card class="panel-card">
          <v-card-title>0. Selecionar requisito/incidente</v-card-title>
          <v-divider />
          <v-card-text>
            <v-row>
              <v-col cols="12" md="5">
                <v-text-field v-model="incidentSearch" label="Buscar requisito" prepend-inner-icon="mdi-magnify" clearable />
              </v-col>
              <v-col cols="12" md="7">
                <v-autocomplete
                  v-model="selectedIncidentId"
                  :items="incidentOptions"
                  :loading="loadingIncidents"
                  item-title="title"
                  item-value="value"
                  label="Requisito/incidente"
                  clearable
                  @update:model-value="selectIncident"
                />
              </v-col>
            </v-row>
            <v-card v-if="selectedIncident" color="surface-variant" variant="tonal" class="mt-2">
              <v-card-text>
                <div class="text-subtitle-1 font-weight-bold">{{ selectedIncident.titulo }}</div>
                <div class="text-body-2 mt-1">{{ selectedIncident.resumo_contexto }}</div>
                <div class="d-flex ga-2 flex-wrap mt-3">
                  <v-chip size="small">Área {{ selectedIncident.modulo }}</v-chip>
                  <v-chip size="small">Sistema {{ selectedIncident.funcionalidade }}</v-chip>
                  <v-chip size="small" color="warning" variant="flat">Urgência {{ selectedIncident.severidade }}</v-chip>
                  <v-chip size="small" color="primary" variant="flat">Score {{ selectedIncident.score_atual }}</v-chip>
                </div>
              </v-card-text>
            </v-card>
          </v-card-text>
        </v-card>

        <v-card class="panel-card mt-4">
          <v-card-title>1. Criar recomendação</v-card-title>
          <v-divider />
          <v-card-text>
            <v-row>
              <v-col cols="12" md="4">
                <v-select v-model="createForm.tipo_recomendacao" :items="recommendationTypes" label="Tipo" />
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field v-model.number="createForm.confianca_ia" type="number" min="0" max="1" step="0.01" label="Confiança" />
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field v-model="createForm.modelo" label="Modelo" />
              </v-col>
              <v-col cols="12">
                <v-text-field v-model="createForm.titulo" label="Título" />
              </v-col>
              <v-col cols="12">
                <v-textarea v-model="createForm.contexto_incidente" label="Contexto" rows="3" />
              </v-col>
              <v-col cols="12">
                <v-textarea v-model="createForm.recomendacao" label="Texto da recomendação" rows="4">
                  <template #append-inner>
                    <v-tooltip text="Gerar com IA" location="top">
                      <template #activator="{ props }">
                        <v-btn
                          v-bind="props"
                          icon="mdi-robot-outline"
                          size="small"
                          variant="text"
                          color="primary"
                          :loading="generating"
                          @click="generateRecommendation"
                        />
                      </template>
                    </v-tooltip>
                  </template>
                </v-textarea>
              </v-col>
            </v-row>
            <div class="d-flex justify-end">
              <v-btn color="primary" prepend-icon="mdi-content-save" :loading="savingCreate" @click="createRecommendation">
                Criar recomendação
              </v-btn>
            </div>
          </v-card-text>
        </v-card>

        <v-row class="mt-1">
          <v-col cols="12" md="6">
            <v-card class="panel-card h-100">
              <v-card-title>2. Registrar decisão</v-card-title>
              <v-divider />
              <v-card-text>
                <v-text-field v-model.number="decisionForm.id_recomendacao" type="number" label="ID da recomendação" />
                <v-select v-model="decisionForm.aceita" :items="booleanOptions" label="Aceita?" />
                <v-text-field v-model="decisionForm.decidido_por" label="Decidido por" />
                <v-textarea v-model="decisionForm.motivo_decisao" label="Motivo" rows="3" />
                <v-btn block color="primary" :loading="savingDecision" @click="saveDecision">Registrar decisão</v-btn>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" md="6">
            <v-card class="panel-card h-100">
              <v-card-title>3. Registrar outcome</v-card-title>
              <v-divider />
              <v-card-text>
                <v-text-field v-model.number="outcomeForm.id_recomendacao" type="number" label="ID da recomendação" />
                <v-select v-model="outcomeForm.foi_aplicada" :items="booleanOptions" label="Aplicada?" />
                <v-text-field v-model="outcomeForm.versao_aplicada" label="Versão aplicada" />
                <v-select v-model="outcomeForm.outcome_positivo" :items="nullableBooleanOptions" label="Outcome positivo?" />
                <v-text-field v-model.number="outcomeForm.score_pos_correcao" type="number" min="0" max="1" step="0.01" label="Score pós-correção" />
                <v-textarea v-model="outcomeForm.observacao" label="Observação" rows="2" />
                <v-btn block color="primary" :loading="savingOutcome" @click="saveOutcome">Registrar outcome</v-btn>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-col>

      <v-col cols="12" lg="5">
        <v-card class="panel-card">
          <v-card-title>Recomendações recentes</v-card-title>
          <v-divider />
          <v-list density="comfortable">
            <v-list-item
              v-for="item in recommendations"
              :key="item.id"
              :title="`#${item.id} · ${item.titulo}`"
              :subtitle="`${item.tipo_recomendacao} · requisito ${item.id_incidente}`"
              prepend-icon="mdi-lightbulb-on-outline"
              @click="selectRecommendation(item.id)"
            />
            <v-list-item v-if="!recommendations.length" title="Nenhuma recomendação criada." />
          </v-list>
        </v-card>

        <v-card class="panel-card mt-4">
          <v-card-title>Detalhe</v-card-title>
          <v-divider />
          <v-card-text v-if="selectedRecommendation">
            <div class="text-subtitle-1 font-weight-bold">{{ selectedRecommendation.titulo }}</div>
            <div class="text-caption text-medium-emphasis">
              ID {{ selectedRecommendation.id }} · requisito {{ selectedRecommendation.id_incidente }}
            </div>
            <p class="mt-3">{{ selectedRecommendation.recomendacao }}</p>
            <div class="d-flex ga-2 flex-wrap mt-3">
              <v-chip size="small">Tipo {{ selectedRecommendation.tipo_recomendacao }}</v-chip>
              <v-chip size="small">Confiança {{ selectedRecommendation.confianca_ia }}</v-chip>
              <v-chip size="small">Score {{ selectedRecommendation.score_inicial ?? '—' }}</v-chip>
            </div>
            <v-divider class="my-4" />
            <div class="text-subtitle-2 mb-2">Decisão</div>
            <div v-if="selectedRecommendation.decisao">
              {{ selectedRecommendation.decisao.aceita ? 'Aceita' : 'Rejeitada' }}
              <span v-if="selectedRecommendation.decisao.decidido_por"> · {{ selectedRecommendation.decisao.decidido_por }}</span>
            </div>
            <div v-else class="text-medium-emphasis">Sem decisão registrada.</div>
            <div class="text-subtitle-2 mt-4 mb-2">Outcome</div>
            <div v-if="selectedRecommendation.outcome">
              {{ selectedRecommendation.outcome.foi_aplicada ? 'Aplicada' : 'Não aplicada' }}
              <span v-if="selectedRecommendation.outcome.versao_aplicada"> · {{ selectedRecommendation.outcome.versao_aplicada }}</span>
              <div class="text-body-2 mt-1">
                Resultado:
                {{ selectedRecommendation.outcome.outcome_positivo === null ? 'Não avaliado' : selectedRecommendation.outcome.outcome_positivo ? 'Positivo' : 'Negativo' }}
              </div>
            </div>
            <div v-else class="text-medium-emphasis">Sem outcome registrado.</div>
          </v-card-text>
          <v-card-text v-else class="text-medium-emphasis">Selecione uma recomendação para ver o detalhe.</v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../services/api'

const loading = ref(false)
const loadingIncidents = ref(false)
const generating = ref(false)
const savingCreate = ref(false)
const savingDecision = ref(false)
const savingOutcome = ref(false)
const errorMessage = ref('')
const windowDays = ref(30)
const metrics = ref(null)
const incidents = ref([])
const incidentSearch = ref('')
const selectedIncidentId = ref(null)
const selectedIncident = ref(null)
const recommendations = ref([])
const selectedRecommendation = ref(null)

const recommendationTypes = [
  { title: 'Hotfix', value: 'hotfix' },
  { title: 'Próx. versão', value: 'proxima_versao' },
  { title: 'Backlog', value: 'backlog' },
  { title: 'Monitorar', value: 'monitorar' },
]
const booleanOptions = [{ title: 'Sim', value: true }, { title: 'Não', value: false }]
const nullableBooleanOptions = [...booleanOptions, { title: 'Não avaliado', value: null }]

const createForm = reactive({
  id_incidente: null,
  titulo: '',
  contexto_incidente: '',
  tipo_recomendacao: 'hotfix',
  confianca_ia: 0.8,
  recomendacao: '',
  modelo: 'gemini-2.5-flash',
  score_inicial: 0.5,
})
const decisionForm = reactive({ id_recomendacao: null, aceita: true, motivo_decisao: '', decidido_por: '' })
const outcomeForm = reactive({
  id_recomendacao: null,
  foi_aplicada: true,
  versao_aplicada: '',
  outcome_positivo: true,
  score_pos_correcao: 0.8,
  observacao: '',
})

const incidentOptions = computed(() => incidents.value.map((item) => ({
  title: `#${item.id} · ${item.titulo}`,
  value: item.id,
  subtitle: `${item.modulo} · ${item.funcionalidade} · ${item.severidade}`,
})))

const metricCards = computed(() => {
  const data = metrics.value || {}
  const acceptance = data.metricas?.taxa_aceitacao?.valor || {}
  const efficacy = data.metricas?.eficacia_pos_correcao?.valor || {}
  const calibration = data.metricas?.calibracao?.valor || {}
  return [
    { title: 'Amostras', value: data.amostras_total ?? 0, subtitle: `${data.janela_dias ?? windowDays.value} dias` },
    { title: 'Aceitação', value: `${Math.round((acceptance.taxa || 0) * 100)}%`, subtitle: `${acceptance.aceitas || 0}/${acceptance.total || 0} decisões` },
    { title: 'Eficácia', value: `${Math.round((efficacy.taxa || 0) * 100)}%`, subtitle: `Brier ${calibration.brier_score ?? 0}` },
  ]
})

function showError(error, fallback) {
  errorMessage.value = error?.response?.data?.detail || error?.response?.data?.errors?.[0]?.message || error?.message || fallback
}

function applyIncidentToForm(item) {
  if (!item) return
  createForm.id_incidente = item.id
  createForm.titulo = item.titulo
  createForm.contexto_incidente = item.resumo_contexto || ''
  createForm.score_inicial = item.score_atual ?? 0.5
}

function fillRecommendationIds(id) {
  decisionForm.id_recomendacao = id
  outcomeForm.id_recomendacao = id
}

async function loadMetrics() {
  const response = await api.get(`/v1/dashboard/ia?janela_dias=${windowDays.value}`)
  metrics.value = response.data
}

async function loadIncidents() {
  loadingIncidents.value = true
  try {
    const params = new URLSearchParams({ limit: '30' })
    if (incidentSearch.value?.trim()) params.set('search', incidentSearch.value.trim())
    const response = await api.get(`/v1/incidentes?${params.toString()}`)
    incidents.value = response.data
  } finally {
    loadingIncidents.value = false
  }
}

async function loadRecommendations() {
  const response = await api.get('/v1/recomendacoes?limit=20')
  recommendations.value = response.data
  if (!selectedRecommendation.value && recommendations.value.length) await selectRecommendation(recommendations.value[0].id)
}

async function loadAll() {
  loading.value = true
  errorMessage.value = ''
  try {
    await Promise.all([loadMetrics(), loadIncidents(), loadRecommendations()])
  } catch (error) {
    showError(error, 'Erro ao carregar recomendações IA.')
  } finally {
    loading.value = false
  }
}

async function selectIncident(id) {
  selectedIncident.value = null
  if (!id) return
  try {
    const response = await api.get(`/v1/incidentes/${id}`)
    selectedIncident.value = response.data
    applyIncidentToForm(selectedIncident.value)
  } catch (error) {
    showError(error, 'Erro ao buscar requisito/incidente.')
  }
}

async function generateRecommendation() {
  if (!createForm.titulo) {
    errorMessage.value = 'Selecione um requisito antes de gerar com IA.'
    return
  }
  generating.value = true
  try {
    const response = await api.post('/v1/ia/gerar-recomendacao', {
      titulo: createForm.titulo,
      contexto_incidente: createForm.contexto_incidente,
      tipo_recomendacao: createForm.tipo_recomendacao,
    })
    createForm.recomendacao = response.data.recomendacao
    createForm.confianca_ia = response.data.confianca_ia
    createForm.modelo = response.data.modelo
  } catch (error) {
    showError(error, 'Erro ao gerar recomendação com IA.')
  } finally {
    generating.value = false
  }
}

async function createRecommendation() {
  if (!createForm.id_incidente) {
    errorMessage.value = 'Selecione um requisito/incidente para criar a recomendação.'
    return
  }
  savingCreate.value = true
  try {
    const response = await api.post('/v1/recomendacoes', { ...createForm })
    await loadRecommendations()
    await loadMetrics()
    await selectRecommendation(response.data.id)
  } catch (error) {
    showError(error, 'Erro ao criar recomendação.')
  } finally {
    savingCreate.value = false
  }
}

async function selectRecommendation(id) {
  const response = await api.get(`/v1/recomendacoes/${id}`)
  selectedRecommendation.value = response.data
  fillRecommendationIds(response.data.id)
}

async function saveDecision() {
  if (!decisionForm.id_recomendacao) return
  savingDecision.value = true
  try {
    await api.post(`/v1/recomendacoes/${decisionForm.id_recomendacao}/decisao`, {
      aceita: decisionForm.aceita,
      motivo_decisao: decisionForm.motivo_decisao || null,
      decidido_por: decisionForm.decidido_por || null,
    })
    await loadRecommendations()
    await loadMetrics()
    await selectRecommendation(decisionForm.id_recomendacao)
  } catch (error) {
    showError(error, 'Erro ao registrar decisão.')
  } finally {
    savingDecision.value = false
  }
}

async function saveOutcome() {
  if (!outcomeForm.id_recomendacao) return
  savingOutcome.value = true
  try {
    await api.post(`/v1/recomendacoes/${outcomeForm.id_recomendacao}/outcome`, {
      foi_aplicada: outcomeForm.foi_aplicada,
      versao_aplicada: outcomeForm.versao_aplicada || null,
      outcome_positivo: outcomeForm.outcome_positivo,
      score_pos_correcao: outcomeForm.score_pos_correcao ?? null,
      observacao: outcomeForm.observacao || null,
    })
    await loadRecommendations()
    await loadMetrics()
    await selectRecommendation(outcomeForm.id_recomendacao)
  } catch (error) {
    showError(error, 'Erro ao registrar outcome.')
  } finally {
    savingOutcome.value = false
  }
}

watch(windowDays, loadMetrics)
watch(incidentSearch, loadIncidents)
onMounted(loadAll)
</script>

<style scoped>
.ai-rec-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.page-header h1 {
  font-size: 1.55rem;
  margin: 0 0 4px;
}

.page-header p {
  margin: 0;
  color: rgba(51, 51, 51, 0.72);
}

.page-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-card {
  border: 1px solid rgba(208, 208, 208, 0.9);
}
</style>
