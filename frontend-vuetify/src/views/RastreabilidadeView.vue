<template>
  <div class="trace-page">
    <section class="page-header">
      <div>
        <div class="text-h5 font-weight-bold mb-1">Rastreabilidade</div>
        <div class="text-body-2 text-medium-emphasis">Encadeamento entre requisito, evento de auditoria e correlation id</div>
      </div>
      <div class="d-flex ga-2 flex-wrap">
        <v-btn variant="outlined" color="primary" :loading="loading" @click="loadTraceability">Atualizar</v-btn>
      </div>
    </section>

    <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4" closable @click:close="errorMessage = ''">{{ errorMessage }}</v-alert>

    <v-alert v-if="loading" type="info" variant="tonal" class="mb-2" icon="mdi-loading mdi-spin">
      Atualizando matriz de rastreabilidade...
    </v-alert>

    <v-row class="mb-4">
      <v-col cols="12" md="4">
        <v-card rounded="xl" :elevation="1" class="pa-4">
          <div class="text-caption text-medium-emphasis">Requisitos</div>
          <div class="text-h6 font-weight-bold">{{ summary.totalRequisitos }}</div>
        </v-card>
      </v-col>
      <v-col cols="12" md="4">
        <v-card rounded="xl" :elevation="1" class="pa-4">
          <div class="text-caption text-medium-emphasis">Com evento rastreado</div>
          <div class="text-h6 font-weight-bold">{{ summary.comEvento }}</div>
        </v-card>
      </v-col>
      <v-col cols="12" md="4">
        <v-card rounded="xl" :elevation="1" class="pa-4">
          <div class="text-caption text-medium-emphasis">Cobertura</div>
          <div class="text-h6 font-weight-bold">{{ summary.cobertura }}%</div>
        </v-card>
      </v-col>
    </v-row>

    <v-card rounded="xl" :elevation="1">
      <v-table>
        <thead>
          <tr>
            <th>Requisito</th>
            <th>Status</th>
            <th>Ação de auditoria</th>
            <th>Correlation ID</th>
            <th>Data evento</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in rows" :key="item.id">
            <td>
              <div class="font-weight-bold">{{ item.codigo }}</div>
              <div class="text-caption text-medium-emphasis">{{ item.titulo }}</div>
            </td>
            <td><v-chip size="small" color="primary" variant="tonal">{{ item.status || '—' }}</v-chip></td>
            <td>{{ item.acao || 'Sem evento' }}</td>
            <td><code>{{ item.correlation_id || '—' }}</code></td>
            <td>{{ formatDate(item.criado_em) }}</td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="5" class="text-center text-medium-emphasis py-6">Nenhum dado de rastreabilidade encontrado.</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'
import { useStatusBanner } from '../composables/useStatusBanner'

const { loading, errorMessage, setLoading, setError } = useStatusBanner()
const rows = ref([])

const summary = computed(() => {
  const totalRequisitos = rows.value.length
  const comEvento = rows.value.filter((item) => item.acao).length
  const cobertura = totalRequisitos ? Math.round((comEvento / totalRequisitos) * 100) : 0
  return { totalRequisitos, comEvento, cobertura }
})

function formatDate(raw) {
  if (!raw) return '—'
  const date = new Date(raw)
  return Number.isNaN(date.getTime()) ? raw : date.toLocaleString('pt-BR')
}

async function loadTraceability() {
  setLoading()
  try {
    const [reqResp, auditResp] = await Promise.all([
      api.get('/v1/requisitos'),
      api.get('/v1/auditoria/eventos', { params: { entidade: 'requisito', limit: 200, offset: 0 } }),
    ])

    const requisitos = reqResp?.data?.data || []
    const eventos = auditResp?.data?.data?.dados || []
    const latestByEntityId = new Map()
    for (const evt of eventos) {
      if (evt?.entidade_id == null) continue
      if (!latestByEntityId.has(evt.entidade_id)) latestByEntityId.set(evt.entidade_id, evt)
    }

    rows.value = requisitos.map((req) => {
      const evento = latestByEntityId.get(req.id)
      return {
        id: req.id,
        codigo: req.codigo,
        titulo: req.titulo,
        status: req.status,
        acao: evento?.acao,
        correlation_id: evento?.correlation_id,
        criado_em: evento?.criado_em,
      }
    })
  } catch (error) {
    setError(error?.response?.data?.detail || error?.message || 'Erro ao carregar rastreabilidade.')
    rows.value = []
  } finally {
    setLoading(false)
  }
}

onMounted(loadTraceability)
</script>

<style scoped>
.trace-page {
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
</style>
