<template>
  <v-card
    class="operational-metric-card"
    :class="{ 'operational-metric-card--clickable': clickable }"
    :data-testid="testId"
    :role="clickable ? 'button' : undefined"
    :tabindex="clickable ? 0 : undefined"
    elevation="0"
    @click="handleClick"
    @keyup.enter="handleClick"
    @keyup.space.prevent="handleClick"
  >
    <v-card-text>
      <div class="card-top">
        <v-icon v-if="icon" :icon="icon" size="18" class="card-icon" />
        <span class="card-label">{{ label }}</span>
        <SemaforoChip v-if="semaforo" :value="semaforo" size="x-small" />
      </div>
      <div class="card-value">{{ value }}</div>
      <p v-if="hint" class="card-hint muted">{{ hint }}</p>
      <div v-if="clickable" class="drilldown-hint">
        <v-icon icon="mdi-open-in-new" size="14" />
        {{ drilldownLabel }}
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import SemaforoChip from './SemaforoChip.vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  semaforo: { type: String, default: '' },
  icon: { type: String, default: '' },
  hint: { type: String, default: '' },
  clickable: { type: Boolean, default: true },
  drilldownLabel: { type: String, default: 'Abrir analítico' },
  testId: { type: String, default: 'operational-metric-card' },
})

const emit = defineEmits(['drilldown'])

function handleClick() {
  if (!props.clickable) return
  emit('drilldown')
}
</script>

<style scoped>
.operational-metric-card {
  height: 100%;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 16px;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
}

.operational-metric-card--clickable {
  cursor: pointer;
}

.operational-metric-card--clickable:hover,
.operational-metric-card--clickable:focus-visible {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--accent, #f39200) 38%, #d0d7de);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
  outline: 2px solid color-mix(in srgb, var(--accent, #f39200) 45%, transparent);
  outline-offset: 2px;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.card-icon {
  color: var(--accent, #f39200);
}

.card-label {
  flex: 1;
  font-size: 13px;
  color: var(--text-muted, #6b7280);
}

.card-value {
  font-size: clamp(24px, 4vw, 32px);
  font-weight: 800;
  margin-top: 8px;
  line-height: 1.1;
}

.card-hint {
  margin: 6px 0 0;
  font-size: 12px;
}

.drilldown-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 10px;
  font-size: 12px;
  font-weight: 700;
  color: var(--accent, #f39200);
}
</style>
