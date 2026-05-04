<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h1>Auditoria</h1>
        <p class="muted audit-subtitle">
          Linha do tempo de eventos relevantes para rastreabilidade, segurança e governança.
        </p>
      </div>
      <v-tooltip text="Eventos demonstrativos da trilha operacional recente" location="top">
        <template #activator="{ props }">
          <v-chip v-bind="props" color="amber" variant="tonal">Últimos eventos</v-chip>
        </template>
      </v-tooltip>
    </div>

    <v-card class="table-card">
      <v-card-title class="py-3 px-4 d-flex align-center ga-2">
        Eventos recentes
        <v-tooltip text="Clique nos chips para inspecionar rapidamente o tipo de registro" location="top">
          <template #activator="{ props }">
            <v-icon v-bind="props" size="18" color="grey">mdi-information-outline</v-icon>
          </template>
        </v-tooltip>
      </v-card-title>
      <v-card-text>
        <v-timeline density="compact" side="end">
          <v-timeline-item v-for="e in eventos" :key="e.id" dot-color="amber">
            <div class="event-row">
              <strong>{{ e.acao }}</strong>
              <v-tooltip text="Identificador de correlação do evento" location="top">
                <template #activator="{ props }">
                  <v-chip v-bind="props" size="x-small" variant="outlined">{{ e.correlation_id }}</v-chip>
                </template>
              </v-tooltip>
            </div>
            <div class="muted">{{ e.quando }} · {{ e.usuario }}</div>
          </v-timeline-item>
        </v-timeline>
      </v-card-text>
    </v-card>
  </section>
</template>

<script setup>
const eventos = [{ id: 1, acao: 'REQUISITO_CRIADO', quando: '2026-04-23 19:00', usuario: 'ericsonjosedossantos@tieri659.onmicrosoft.com', correlation_id: 'demo-123' }]
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

