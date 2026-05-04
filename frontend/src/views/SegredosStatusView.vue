<template>
  <section class="page">
    <PageHeader
      title="Status de Segredos"
      subtitle="Diagnóstico da origem dos segredos do backend, sem exposição de valores."
      :chip="statusChipText"
      :chip-color="statusChipColor"
      chip-tooltip="Indica a origem predominante dos segredos configurados"
    >
      <template #actions>
        <v-tooltip text="Recarrega o diagnóstico de segredos do backend" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              variant="outlined"
              prepend-icon="mdi-refresh"
              :loading="carregando"
              data-testid="btn-atualizar"
              @click="carregar"
            >
              Atualizar
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Abre o cofre para gerenciar segredos diretamente" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              color="amber"
              variant="tonal"
              prepend-icon="mdi-safe"
              href="/cofre.html"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="btn-abrir-cofre"
            >
              Abrir cofre
            </v-btn>
          </template>
        </v-tooltip>
      </template>
    </PageHeader>

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4" data-testid="alerta-erro">
      {{ erro }}
    </v-alert>

    <v-row>
      <!-- Resumo / KPIs -->
      <v-col cols="12" md="4">
        <v-card class="table-card h-100">
          <v-card-title class="py-3 px-4">Resumo</v-card-title>
          <v-divider />
          <v-card-text>
            <v-skeleton-loader v-if="carregando" type="list-item-three-line" />
            <div v-else class="summary-grid">
              <div class="summary-item">
                <div class="muted">Total monitorado</div>
                <strong class="summary-value" data-testid="total">{{ total }}</strong>
              </div>
              <div class="summary-item">
                <div class="muted">Via ambiente</div>
                <strong class="summary-value">{{ countBySource.env }}</strong>
              </div>
              <div class="summary-item">
                <div class="muted">Via cofre</div>
                <strong class="summary-value">{{ countBySource.vault }}</strong>
              </div>
              <div class="summary-item">
                <div class="muted">Usando default</div>
                <strong class="summary-value" :class="{ 'text-amber': countBySource.default > 0 }">
                  {{ countBySource.default }}
                </strong>
              </div>
            </div>

            <v-alert type="info" variant="tonal" class="mt-4" density="compact">
              Os valores dos segredos <strong>nunca</strong> são retornados pela API —
              apenas a origem da configuração.
            </v-alert>

            <v-alert
              v-if="!carregando && countBySource.default > 0"
              type="warning"
              variant="tonal"
              class="mt-3"
              density="compact"
              data-testid="alerta-default"
            >
              {{ countBySource.default }} segredo(s) usando valor padrão. Considere configurar via ambiente ou cofre.
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Tabela de segredos -->
      <v-col cols="12" md="8">
        <v-card class="table-card">
          <v-card-title class="py-3 px-4">Segredos monitorados</v-card-title>
          <v-divider />

          <v-skeleton-loader v-if="carregando" type="table-row-divider@5" />
          <v-table v-else data-testid="tabela-segredos">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Origem</th>
                <th>Resolvido</th>
                <th>Cofre / Serviço</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="segredo in segredos" :key="segredo.name" :data-testid="`row-${segredo.name}`">
                <td>
                  <div class="secret-name">{{ segredo.name }}</div>
                  <div class="muted text-caption">env: {{ segredo.env_name || segredo.name }}</div>
                </td>
                <td>
                  <StatusChip
                    :value="segredo.source"
                    :tooltip="sourceTooltip(segredo.source)"
                    data-testid="chip-origem"
                  />
                </td>
                <td>
                  <v-tooltip :text="segredo.resolved ? 'Valor disponível' : 'Não configurado'" location="top">
                    <template #activator="{ props }">
                      <v-icon
                        v-bind="props"
                        :icon="segredo.resolved ? 'mdi-check-circle' : 'mdi-alert-circle'"
                        :color="segredo.resolved ? 'green' : 'grey'"
                        size="20"
                        :data-testid="`resolved-${segredo.name}`"
                      />
                    </template>
                  </v-tooltip>
                </td>
                <td>
                  <span v-if="segredo.vault_key" class="text-caption">
                    <strong>{{ segredo.vault_key }}</strong>
                    <span v-if="segredo.vault_service_name" class="muted"> · {{ segredo.vault_service_name }}</span>
                  </span>
                  <span v-else class="muted">—</span>
                </td>
              </tr>
              <tr v-if="!segredos.length">
                <td colspan="4" class="empty-cell">Nenhum diagnóstico retornado.</td>
              </tr>
            </tbody>
          </v-table>
        </v-card>
      </v-col>
    </v-row>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../services/api'
import PageHeader from '../components/PageHeader.vue'
import StatusChip from '../components/StatusChip.vue'
import { useAsyncLoader } from '../composables/useAsyncLoader.js'

const { carregando, erro, run } = useAsyncLoader()

const segredos = ref([])
const total = ref(0)

const countBySource = computed(() => {
  const counts = { env: 0, vault: 0, default: 0, absent: 0 }
  for (const s of segredos.value) {
    const source = s?.source || 'absent'
    if (source in counts) counts[source] += 1
  }
  return counts
})

const statusChipText = computed(() => {
  if (erro.value) return 'Falha de leitura'
  if (countBySource.value.vault > 0) return 'Cofre em uso'
  if (countBySource.value.env > 0) return 'Ambiente em uso'
  return 'Aguardando diagnóstico'
})

const statusChipColor = computed(() => {
  if (erro.value) return 'red'
  if (countBySource.value.vault > 0) return 'green'
  if (countBySource.value.env > 0) return 'amber'
  return 'grey'
})

function sourceTooltip(source) {
  return {
    env:     'Lido de variável de ambiente',
    vault:   'Lido do cofre de segredos encriptado',
    default: 'Usando valor padrão — configure via ambiente ou cofre',
    absent:  'Não configurado em nenhuma origem',
  }[source] || source
}

async function carregar() {
  await run(async () => {
    const { data } = await api.get('/v1/sistema/segredos-status')
    const payload = data?.data || {}
    segredos.value = payload.segredos || []
    total.value = payload.total || segredos.value.length
  })
}

onMounted(carregar)
</script>

<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.summary-item {
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
}

.summary-value {
  font-size: 1.4rem;
  font-weight: 700;
}

.text-amber {
  color: rgb(var(--v-theme-amber));
}

.secret-name {
  font-weight: 600;
}

.empty-cell {
  text-align: center;
  color: var(--muted);
  padding: 24px 12px;
}
</style>
