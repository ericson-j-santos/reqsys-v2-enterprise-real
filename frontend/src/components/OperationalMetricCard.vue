<template>
  <article
    class="operational-metric-card"
    :class="{ 'operational-metric-card--clickable': clickable }"
    :data-testid="testId"
    :role="clickable ? 'button' : undefined"
    :tabindex="clickable ? 0 : undefined"
    @click="handleClick"
    @keyup.enter="handleClick"
    @keyup.space.prevent="handleClick"
  >
    <div class="card-top">
      <v-icon v-if="icon" :icon="icon" size="18" class="card-icon" />
      <span class="card-label">{{ label }}</span>
      <SemaforoChip v-if="semaforo" :value="semaforo" variant="figma" :show-icon="false" />
    </div>
    <div class="card-value">{{ value }}</div>
    <p v-if="hint" class="card-hint">{{ hint }}</p>
    <div v-if="clickable" class="drilldown-hint">
      <span aria-hidden="true">↗</span>
      {{ drilldownLabel }}
    </div>
  </article>
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
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.02);
  min-height: 148px;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
}

.operational-metric-card--clickable {
  cursor: pointer;
}

.operational-metric-card--clickable:hover,
.operational-metric-card--clickable:focus-visible {
  transform: translateY(-2px);
  border-color: rgba(243, 146, 0, 0.45);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.22);
  outline: none;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 13px;
}

.card-icon {
  color: var(--muted);
}

.card-label {
  flex: 1;
  min-width: 0;
}

.card-value {
  font-size: 32px;
  font-weight: 800;
  margin: 10px 0 6px;
  line-height: 1.1;
  color: var(--text);
}

.card-hint {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}

.drilldown-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 10px;
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
}
</style>
