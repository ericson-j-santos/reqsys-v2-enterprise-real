<template>
  <section class="page">
    <PageHeader
      title="Monitoramento de Qualidade de IA"
      subtitle="Acompanhe score geral, métricas-chave, tendência histórica e recomendações para melhoria contínua."
      :chip="statusLabel"
      :chip-color="statusColor"
      chip-tooltip="Status operacional atual da qualidade de IA"
    >
      <template #actions>
        <v-tooltip text="Executa um novo snapshot do monitoramento de qualidade" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              color="amber"
              variant="tonal"
              prepend-icon="mdi-camera"
              :loading="salvandoSnapshot"
              @click="gerarSnapshot"
            >
              Gerar snapshot
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Recarrega dados do monitoramento de qualidade" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              variant="outlined"
              prepend-icon="mdi-refresh"
              :loading="carregando"
              @click="carregar"
            >
              Atualizar
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Período do histórico para exportação/tendência" location="top">
          <template #activator="{ props }">
            <v-btn-toggle
              v-bind="props"
              v-model="periodoFiltro"
              density="compact"
              variant="outlined"
              divided
              mandatory
            >
              <v-btn :value="7" size="small">7d</v-btn>
              <v-btn :value="30" size="small">30d</v-btn>
              <v-btn :value="90" size="small">90d</v-btn>
              <v-btn :value="null" size="small">Todos</v-btn>
            </v-btn-toggle>
          </template>
        </v-tooltip>
        <v-tooltip text="Exporta tendência histórica em CSV" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              variant="outlined"
              prepend-icon="mdi-file-delimited"
              :loading="exportandoCsv"
              @click="exportarCsv"
            >
              CSV
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Exporta tendência histórica em PDF" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              variant="outlined"
              prepend-icon="mdi-file-pdf-box"
              :loading="exportandoPdf"
              @click="exportarPdf"
            >
              PDF
            </v-btn>
          </template>
        </v-tooltip>
      </template>
    </PageHeader>

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4">
      {{ erro }}
    </v-alert>

    <v-alert
      v-if="guardrail100"
      :type="guardrail100.passou ? 'success' : 'warning'"
      variant="tonal"
      class="mb-4"
    >
      <div class="font-weight-medium">Guard rail de Qualidade IA: meta 100%</div>
      <div>{{ guardrail100.mensagem }}</div>
      <div v-if="guardrail100.gaps?.length" class="mt-2 text-caption">
        Gaps: {{ guardrail100.gaps.map((item) => `${item.metrica} -${item.gap}%`).join(', ') }}
      </div>
    </v-alert>

    <!-- Providers IA -->
    <v-row class="mb-1">
      <v-col cols="12">
        <v-card class="table-card">
          <v-card-title class="d-flex align-center justify-space-between">
            <span>Providers IA</span>
            <v-chip
              :color="statusIA.fallback_ativo ? 'green' : 'amber'"
              size="small"
              variant="tonal"
            >
              <v-icon start size="14">{{ statusIA.fallback_ativo ? 'mdi-shield-check' : 'mdi-shield-alert' }}</v-icon>
              {{ statusIA.fallback_ativo ? 'Fallback ativo' : 'Fallback inativo' }}
            </v-chip>
          </v-card-title>
          <v-divider />
          <v-card-text>
            <v-row>
              <!-- Gemini -->
              <v-col cols="12" md="6">
                <div class="provider-header">
                  <v-icon :color="statusIA.provedores?.gemini?.configurado ? 'green' : 'red'" size="20">
                    {{ statusIA.provedores?.gemini?.configurado ? 'mdi-check-circle' : 'mdi-close-circle' }}
                  </v-icon>
                  <strong class="ml-2">Gemini</strong>
                  <v-chip size="x-small" color="blue" variant="tonal" class="ml-2">Primário</v-chip>
                  <span class="muted ml-auto" style="font-size:0.8rem">{{ statusIA.provedores?.gemini?.modelo }}</span>
                </div>
                <div v-if="statusIA.provedores?.gemini?.configurado" class="mt-2">
                  <div class="cota-row">
                    <span class="muted">Hoje</span>
                    <span>{{ statusIA.provedores.gemini.cota.req_hoje }} / {{ statusIA.provedores.gemini.cota.limite_por_dia }}</span>
                  </div>
                  <v-progress-linear
                    :model-value="statusIA.provedores.gemini.cota.pct_dia_usado"
                    color="blue"
                    bg-color="blue-lighten-4"
                    rounded
                    height="8"
                    class="my-1"
                  />
                  <div class="cota-row muted" style="font-size:0.78rem">
                    <span>Restante hoje: {{ statusIA.provedores.gemini.cota.restante_dia }} req</span>
                    <span>{{ statusIA.provedores.gemini.cota.restante_minuto }}/min disponíveis</span>
                  </div>
                </div>
                <v-alert v-else type="warning" variant="tonal" density="compact" class="mt-2" style="font-size:0.82rem">
                  GEMINI_API_KEY não configurada
                </v-alert>
              </v-col>

              <!-- Groq -->
              <v-col cols="12" md="6">
                <div class="provider-header">
                  <v-icon :color="statusIA.provedores?.groq?.configurado ? 'green' : 'grey'" size="20">
                    {{ statusIA.provedores?.groq?.configurado ? 'mdi-check-circle' : 'mdi-circle-outline' }}
                  </v-icon>
                  <strong class="ml-2">Groq / Llama</strong>
                  <v-chip size="x-small" color="purple" variant="tonal" class="ml-2">Fallback</v-chip>
                  <span class="muted ml-auto" style="font-size:0.8rem">{{ statusIA.provedores?.groq?.modelo }}</span>
                </div>
                <div v-if="statusIA.provedores?.groq?.configurado" class="mt-2">
                  <div class="cota-row">
                    <span class="muted">Hoje</span>
                    <span>{{ statusIA.provedores.groq.cota.req_hoje }} / {{ statusIA.provedores.groq.cota.limite_por_dia }}</span>
                  </div>
                  <v-progress-linear
                    :model-value="statusIA.provedores.groq.cota.pct_dia_usado"
                    color="purple"
                    bg-color="purple-lighten-4"
                    rounded
                    height="8"
                    class="my-1"
                  />
                  <div class="cota-row muted" style="font-size:0.78rem">
                    <span>Restante hoje: {{ statusIA.provedores.groq.cota.restante_dia }} req</span>
                    <span>{{ statusIA.provedores.groq.cota.restante_minuto }}/min disponíveis</span>
                  </div>
                </div>
                <v-alert v-else type="info" variant="tonal" density="compact" class="mt-2" style="font-size:0.82rem">
                  GROQ_API_KEY não configurada — fallback desativado.
                  <a href="https://console.groq.com" target="_blank" class="ml-1">Obter grátis</a>
                </v-alert>
              </v-col>
            </v-row>

            <!-- Passos pendentes -->
            <div v-if="statusIA.passos_pendentes?.length" class="mt-3">
              <v-divider class="mb-3" />
              <div class="d-flex align-center mb-2">
                <v-icon color="amber" size="18" class="mr-1">mdi-clipboard-list-outline</v-icon>
                <strong style="font-size:0.9rem">Passos pendentes para o desenvolvedor</strong>
              </div>
              <v-list density="compact" class="pa-0">
                <v-list-item
                  v-for="(item, i) in statusIA.passos_pendentes"
                  :key="i"
                  class="pa-0"
                >
                  <template #prepend>
                    <v-icon
                      :color="item.prioridade === 'alta' ? 'red' : 'amber'"
                      size="16"
                      class="mr-2"
                    >
                      {{ item.prioridade === 'alta' ? 'mdi-alert-circle' : 'mdi-information' }}
                    </v-icon>
                  </template>
                  <v-list-item-title style="font-size:0.88rem; white-space:normal">
                    {{ item.passo }}
                  </v-list-item-title>
                  <v-list-item-subtitle style="font-size:0.78rem">{{ item.detalhe }}</v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12" md="4">
        <v-card class="table-card h-100">
          <v-card-title>Score geral</v-card-title>
          <v-divider />
          <v-card-text>
            <div class="score-wrap">
              <v-progress-circular
                :model-value="scoreGeral"
                :size="132"
                :width="14"
                :color="statusColor"
              >
                <strong>{{ scoreGeral }}%</strong>
              </v-progress-circular>
              <div class="mt-3 muted">Amostra analisada: {{ resumo.contexto?.amostra_total ?? 0 }}</div>
              <div class="muted">Incidentes críticos (7d): {{ resumo.contexto?.incidentes_criticos_7d ?? 0 }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="8">
        <v-card class="table-card h-100">
          <v-card-title>Métricas de qualidade</v-card-title>
          <v-divider />
          <v-card-text>
            <v-row>
              <v-col v-for="item in metricasList" :key="item.key" cols="12" sm="6">
                <div class="metric-head-row">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}%</strong>
                </div>
                <v-progress-linear
                  :model-value="item.value"
                  :color="item.color"
                  rounded
                  height="10"
                />
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-1">
      <v-col cols="12" lg="8">
        <v-card class="table-card">
          <v-card-title>
            Tendência histórica
            <v-chip v-if="periodoFiltro" size="x-small" class="ml-2" color="amber" variant="tonal">
              {{ periodoFiltro }}d
            </v-chip>
          </v-card-title>
          <v-divider />
          <v-card-text>
            <v-sparkline
              v-if="tendenciaValues.length"
              :model-value="tendenciaValues"
              color="amber"
              line-width="2"
              auto-draw
              padding="8"
              smooth
              :fill="false"
            />
            <div v-else class="muted">Ainda não existem snapshots para exibir tendência.</div>

            <v-table class="mt-3" density="compact">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Score</th>
                  <th>Acurácia</th>
                  <th>Segurança</th>
                  <th>Incidentes</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in tendencia" :key="item.id">
                  <td>{{ formatDate(item.timestamp) }}</td>
                  <td><strong>{{ item.score_geral }}%</strong></td>
                  <td>{{ item.acuracia }}%</td>
                  <td>{{ item.seguranca }}%</td>
                  <td>{{ item.incidentes_criticos }}</td>
                </tr>
                <tr v-if="!tendencia.length">
                  <td colspan="5" class="empty-cell">Nenhum snapshot disponível.</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="4">
        <v-card class="table-card">
          <v-card-title>Recomendações</v-card-title>
          <v-divider />
          <v-list density="compact">
            <v-list-item
              v-for="(item, idx) in recomendacoes"
              :key="`${idx}-${item}`"
              :title="item"
              prepend-icon="mdi-lightbulb-on-outline"
            />
            <v-list-item v-if="!recomendacoes.length" title="Sem recomendações no momento." />
          </v-list>
        </v-card>
      </v-col>
    </v-row>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../services/api'
import { qualidadeIAService } from '../services/qualidadeIA'
import PageHeader from '../components/PageHeader.vue'
import { useAsyncLoader } from '../composables/useAsyncLoader'

const { carregando, erro, run } = useAsyncLoader()

const resumo = ref({})
const statusIA = ref({ provedores: {}, fallback_ativo: false, passos_pendentes: [] })
const salvandoSnapshot = ref(false)
const exportandoCsv = ref(false)
const exportandoPdf = ref(false)
const periodoFiltro = ref(30)

const scoreGeral = computed(() => Math.round(resumo.value?.score_geral || 0))
const tendencia = computed(() => resumo.value?.tendencia || [])
const recomendacoes = computed(() => resumo.value?.recomendacoes || [])
const guardrail100 = computed(() => resumo.value?.guardrail_100 || null)

const tendenciaValues = computed(() => tendencia.value.map((i) => Number(i.score_geral || 0)))

const metricasList = computed(() => {
  const m = resumo.value?.metricas || {}
  return [
    { key: 'acuracia', label: 'Acurácia', value: Number(m.acuracia || 0), color: 'blue' },
    { key: 'relevancia', label: 'Relevância', value: Number(m.relevancia || 0), color: 'purple' },
    { key: 'consistencia', label: 'Consistência', value: Number(m.consistencia || 0), color: 'teal' },
    { key: 'seguranca', label: 'Segurança', value: Number(m.seguranca || 0), color: 'green' },
    { key: 'cobertura_dados', label: 'Cobertura de dados', value: Number(m.cobertura_dados || 0), color: 'amber' },
  ]
})

const statusLabel = computed(() => {
  const value = resumo.value?.status || 'desconhecido'
  return value.charAt(0).toUpperCase() + value.slice(1)
})

const statusColor = computed(() => {
  const value = resumo.value?.status
  if (value === 'excelente') return 'green'
  if (value === 'estavel') return 'blue'
  if (value === 'atencao') return 'amber'
  if (value === 'critico') return 'red'
  return 'grey'
})

function formatDate(raw) {
  if (!raw) return '—'
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleString('pt-BR')
}

async function carregar() {
  await run(async () => {
    const params = periodoFiltro.value != null ? `?dias=${periodoFiltro.value}` : ''
    const [{ data: dataQualidade }, { data: dataIA }] = await Promise.all([
      api.get(`/v1/qualidade-ia/resumo${params}`),
      api.get('/v1/ia/status'),
    ])
    resumo.value = dataQualidade?.data || {}
    statusIA.value = dataIA?.data || { provedores: {}, fallback_ativo: false, passos_pendentes: [] }
  })
}

watch(periodoFiltro, carregar)

async function gerarSnapshot() {
  salvandoSnapshot.value = true
  try {
    await api.post('/v1/qualidade-ia/snapshot')
    await carregar()
  } catch {
    // Erro já tratado por carregar() na atualização posterior.
  } finally {
    salvandoSnapshot.value = false
  }
}

async function exportarCsv() {
  exportandoCsv.value = true
  try {
    await qualidadeIAService.baixarTendenciaCsv(200, periodoFiltro.value)
  } finally {
    exportandoCsv.value = false
  }
}

async function exportarPdf() {
  exportandoPdf.value = true
  try {
    await qualidadeIAService.baixarTendenciaPdf(200, periodoFiltro.value)
  } finally {
    exportandoPdf.value = false
  }
}

onMounted(carregar)
</script>

<style scoped>
.score-wrap {
  display: grid;
  place-items: center;
  text-align: center;
}

.metric-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 0.92rem;
}

.empty-cell {
  text-align: center;
  color: var(--muted);
  padding: 18px;
}

.provider-header {
  display: flex;
  align-items: center;
  font-size: 0.95rem;
}

.cota-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.83rem;
}
</style>
