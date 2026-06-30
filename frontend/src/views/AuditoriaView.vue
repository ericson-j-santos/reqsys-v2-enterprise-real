<template>
  <section class="page" data-testid="route-auditoria">
    <div class="page-header">
      <div>
        <h1>Auditoria</h1>
        <p class="muted audit-subtitle">
          Linha do tempo de eventos relevantes para rastreabilidade, segurança e governança.
        </p>
      </div>
      <div class="header-actions">
        <v-btn variant="outlined" prepend-icon="mdi-refresh" :loading="carregando" @click="carregarEventos">
          Atualizar
        </v-btn>
      </div>
    </div>

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4" role="alert">{{ erro }}</v-alert>

    <v-card class="table-card">
      <v-card-title class="py-3 px-4 d-flex align-center ga-2">
        Eventos recentes
        <v-chip v-if="totalEventos" size="small" variant="tonal" color="amber">{{ totalEventos }} registros</v-chip>
        <v-tooltip text="Clique nos chips para inspecionar rapidamente o tipo de registro" location="top">
          <template #activator="{ props }">
            <v-icon v-bind="props" size="18" color="grey">mdi-information-outline</v-icon>
          </template>
        </v-tooltip>
      </v-card-title>
      <v-card-text>
        <div v-if="carregando" class="muted">Carregando eventos de auditoria...</div>
        <div v-else-if="!eventos.length" class="muted">Nenhum evento de auditoria registrado ainda.</div>
        <v-timeline v-else density="compact" side="end">
          <v-timeline-item v-for="e in eventos" :key="e.id" dot-color="amber">
            <div class="event-row">
              <strong>{{ e.acao }}</strong>
              <v-chip v-if="e.entidade" size="x-small" variant="tonal">{{ e.entidade }}</v-chip>
              <v-tooltip text="Identificador de correlação do evento" location="top">
                <template #activator="{ props }">
                  <v-chip v-bind="props" size="x-small" variant="outlined">{{ e.correlation_id }}</v-chip>
                </template>
              </v-tooltip>
            </div>
            <div class="muted">{{ formatarQuando(e.criado_em) }} · {{ e.usuario || 'sistema' }}</div>
          </v-timeline-item>
        </v-timeline>
      </v-card-text>
    </v-card>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const eventos = ref([])
const totalEventos = ref(0)
const carregando = ref(false)
const erro = ref('')

function formatarQuando(valor) {
  if (!valor) return '-'
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return valor
  return data.toLocaleString('pt-BR')
}

async function carregarEventos() {
  carregando.value = true
  erro.value = ''
  try {
    const { data: payload } = await api.get('/v1/auditoria/eventos', { params: { limit: 50 } })
    eventos.value = payload.data?.dados || []
    totalEventos.value = payload.data?.paginacao?.total ?? eventos.value.length
  } catch (e) {
    erro.value = e?.response?.data?.detail || e?.message || 'Falha ao carregar eventos de auditoria'
    eventos.value = []
    totalEventos.value = 0
  } finally {
    carregando.value = false
  }
}

onMounted(carregarEventos)
</script>

<style scoped>
.audit-subtitle {
  max-width: 58ch;
}

.event-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
