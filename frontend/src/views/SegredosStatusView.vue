<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h1>Status de Segredos</h1>
        <p class="muted secrets-subtitle">
          Diagnóstico da origem dos segredos do backend, sem exposição de valores.
        </p>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <v-btn
          size="small"
          variant="outlined"
          prepend-icon="mdi-refresh"
          :loading="carregando"
          @click="carregar"
        >
          Atualizar
        </v-btn>
        <v-chip size="small" :color="statusChipColor" variant="tonal">
          {{ statusChipText }}
        </v-chip>
      </div>
    </div>

    <v-row>
      <v-col cols="12" md="4">
        <v-card class="table-card metric-card">
          <v-card-title class="py-3 px-4">Resumo</v-card-title>
          <v-divider />
          <v-card-text>
            <div class="summary-grid">
              <div class="summary-item">
                <div class="muted">Total monitorado</div>
                <strong>{{ total }}</strong>
              </div>
              <div class="summary-item">
                <div class="muted">Via ambiente</div>
                <strong>{{ countBySource.env }}</strong>
              </div>
              <div class="summary-item">
                <div class="muted">Via cofre</div>
                <strong>{{ countBySource.vault }}</strong>
              </div>
              <div class="summary-item">
                <div class="muted">Usando default</div>
                <strong>{{ countBySource.default }}</strong>
              </div>
            </div>

            <v-alert v-if="erro" type="error" variant="tonal" class="mt-4">
              {{ erro }}
            </v-alert>

            <v-alert type="info" variant="tonal" class="mt-4">
              Este painel informa apenas a origem da configuração. Os valores não são retornados pela API.
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="8">
        <v-card class="table-card">
          <v-card-title class="py-3 px-4">Segredos monitorados</v-card-title>
          <v-divider />
          <v-table>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Origem</th>
                <th>Chave do cofre</th>
                <th>Serviço</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="segredo in segredos" :key="segredo.name">
                <td>
                  <div class="secret-name">{{ segredo.name }}</div>
                  <div class="muted text-caption">env: {{ segredo.env_name }}</div>
                </td>
                <td>
                  <v-chip size="small" :color="sourceColor(segredo.source)" variant="tonal">
                    {{ sourceLabel(segredo.source) }}
                  </v-chip>
                </td>
                <td>{{ segredo.vault_key || '—' }}</td>
                <td>{{ segredo.vault_service_name || '—' }}</td>
              </tr>
              <tr v-if="!segredos.length && !carregando">
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

const carregando = ref(false)
const erro = ref('')
const segredos = ref([])
const total = ref(0)

const countBySource = computed(() => {
  const counts = { env: 0, vault: 0, default: 0, absent: 0 }
  for (const segredo of segredos.value) {
    const source = segredo?.source || 'absent'
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

function sourceLabel(source) {
  return {
    env: 'Ambiente',
    vault: 'Cofre',
    default: 'Default',
    absent: 'Ausente',
  }[source] || source
}

function sourceColor(source) {
  return {
    env: 'amber',
    vault: 'green',
    default: 'blue',
    absent: 'grey',
  }[source] || 'grey'
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const { data } = await api.get('/v1/sistema/segredos-status')
    const payload = data?.data || {}
    segredos.value = payload.segredos || []
    total.value = payload.total || segredos.value.length
  } catch (e) {
    erro.value = e?.response?.data?.errors?.[0]?.message || e?.message || 'Falha ao carregar status de segredos.'
    segredos.value = []
    total.value = 0
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)
</script>

<style scoped>
.secrets-subtitle {
  max-width: 60ch;
}

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

.metric-card {
  height: 100%;
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