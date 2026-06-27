<template>
  <v-card class="drilldown-bar" variant="tonal" elevation="0" data-testid="operational-drilldown-bar">
    <v-card-text class="drilldown-bar-inner">
      <nav class="trail" aria-label="Trilha analítica">
        <button
          v-for="(crumb, index) in breadcrumbs"
          :key="`${crumb.path}-${index}`"
          type="button"
          class="trail-item"
          @click="emit('navigate', crumb)"
        >
          <span v-if="index > 0" class="trail-sep">›</span>
          {{ crumb.label }}
        </button>
      </nav>

      <div class="meta">
        <v-chip v-if="correlationId" size="x-small" variant="outlined" data-testid="drilldown-correlation-id">
          correlation_id: {{ correlationId }}
        </v-chip>
        <v-chip
          v-for="filtro in filtrosAtivos"
          :key="filtro.key"
          size="x-small"
          color="amber"
          variant="tonal"
          closable
          :data-testid="`drilldown-filter-${filtro.key}`"
          @click:close="emit('remove-filter', filtro.key)"
        >
          {{ filtro.label }}: {{ filtro.value }}
        </v-chip>
        <v-btn
          v-if="possuiFiltros"
          size="x-small"
          variant="text"
          data-testid="drilldown-clear-filters"
          @click="emit('clear-filters')"
        >
          Limpar filtros
        </v-btn>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
defineProps({
  breadcrumbs: { type: Array, default: () => [] },
  filtrosAtivos: { type: Array, default: () => [] },
  possuiFiltros: { type: Boolean, default: false },
  correlationId: { type: String, default: '' },
})

const emit = defineEmits(['navigate', 'remove-filter', 'clear-filters'])
</script>

<style scoped>
.drilldown-bar {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 14px;
  margin-bottom: 12px;
}

.drilldown-bar-inner {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.trail {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.trail-item {
  background: none;
  border: none;
  padding: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--accent, #f39200);
  cursor: pointer;
}

.trail-sep {
  margin: 0 6px;
  color: var(--text-muted, #6b7280);
  font-weight: 400;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

@media (max-width: 600px) {
  .trail-item { font-size: 12px; }
}
</style>
