<template>
  <v-card class="incident-panel" elevation="0" data-testid="incident-timeline-panel">
    <v-card-title class="panel-title">
      <span>Incident Timeline</span>
      <SemaforoChip :value="semaforoTimeline" size="small" />
    </v-card-title>
    <v-card-subtitle>Timeline viva correlacionada com filtros preservados e drill-down operacional.</v-card-subtitle>
    <v-card-text>
      <div class="filters">
        <v-select
          v-model="filtroTipo"
          :items="tiposEvento"
          label="Tipo de evento"
          clearable
          variant="outlined"
          density="compact"
          hide-details
          data-testid="incident-filter-type"
        />
        <v-select
          v-model="filtroSeveridade"
          :items="severidades"
          label="Severidade"
          clearable
          variant="outlined"
          density="compact"
          hide-details
          data-testid="incident-filter-severity"
        />
      </div>

      <v-timeline v-if="eventosFiltrados.length" density="compact" side="end" class="mt-3">
        <v-timeline-item
          v-for="evento in eventosFiltrados"
          :key="evento.id"
          :dot-color="corEvento(evento)"
          data-testid="incident-timeline-item"
        >
          <div class="event-row">
            <div>
              <strong>{{ rotuloEvento(evento.event_type) }}</strong>
              <div class="muted">{{ formatarData(evento.occurred_at || evento.event_at) }}</div>
              <div class="muted">status: {{ evento.status }} · {{ evento.correlation_id || 'sem correlation' }}</div>
            </div>
            <div class="event-actions">
              <SemaforoChip :value="evento.status || evento.severity" size="x-small" />
              <v-btn
                size="small"
                variant="tonal"
                color="amber"
                data-testid="incident-drilldown-btn"
                @click="emit('drilldown', evento)"
              >
                Detalhar
              </v-btn>
            </div>
          </div>
        </v-timeline-item>
      </v-timeline>

      <v-alert v-else type="info" variant="tonal" class="mt-3" data-testid="incident-timeline-empty">
        Nenhum incidente correlacionado no snapshot atual. A timeline será populada conforme eventos runtime forem registrados.
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed, ref } from 'vue'
import SemaforoChip from './SemaforoChip.vue'

const props = defineProps({
  eventos: { type: Array, default: () => [] },
})

const emit = defineEmits(['drilldown'])

const filtroTipo = ref(null)
const filtroSeveridade = ref(null)

const tiposEvento = [
  { title: 'Incidente aberto', value: 'incident_opened' },
  { title: 'Incidente reconhecido', value: 'incident_acknowledged' },
  { title: 'Incidente resolvido', value: 'incident_resolved' },
]

const severidades = [
  { title: 'Alta', value: 'high' },
  { title: 'Média', value: 'medium' },
  { title: 'Baixa', value: 'low' },
]

const eventosFiltrados = computed(() => props.eventos.filter((evento) => {
  if (filtroTipo.value && evento.event_type !== filtroTipo.value) return false
  if (filtroSeveridade.value && evento.severity !== filtroSeveridade.value) return false
  return true
}))

const semaforoTimeline = computed(() => {
  const abertos = props.eventos.filter((e) => ['incident_opened', 'incident_acknowledged'].includes(e.event_type))
  if (abertos.length > 0) return 'vermelho'
  if (props.eventos.length > 0) return 'verde'
  return 'desconhecido'
})

function corEvento(evento) {
  if (['incident_opened', 'incident_acknowledged'].includes(evento.event_type)) return 'red'
  if (evento.event_type === 'incident_resolved') return 'green'
  return 'amber'
}

function rotuloEvento(tipo) {
  const map = {
    incident_opened: 'Incidente aberto',
    incident_acknowledged: 'Incidente reconhecido',
    incident_resolved: 'Incidente resolvido',
  }
  return map[tipo] || tipo || 'Evento operacional'
}

function formatarData(valor) {
  if (!valor) return '-'
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return valor
  return data.toLocaleString('pt-BR')
}
</script>

<style scoped>
.incident-panel {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 16px;
}

.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.event-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.event-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.muted {
  color: var(--text-muted, #6b7280);
  font-size: 12px;
}
</style>
