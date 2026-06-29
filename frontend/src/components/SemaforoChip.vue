<!--
  SemaforoChip — semáforo operacional canônico (verde / amarelo / vermelho / bloqueado).
  variant="figma" alinha badges a docs/dashboard/figma/.
-->
<template>
  <span
    v-if="variant === 'figma'"
    class="figma-badge"
    :class="`figma-badge--${resolved.key}`"
    :data-testid="`semaforo-${resolved.key}`"
  >
    {{ resolved.label }}
  </span>
  <v-chip
    v-else
    :size="size"
    :color="resolved.color"
    :variant="variant"
    :data-testid="`semaforo-${resolved.key}`"
  >
    <v-icon v-if="showIcon" :icon="resolved.icon" size="14" class="mr-1" />
    {{ resolved.label }}
  </v-chip>
</template>

<script setup>
import { computed } from 'vue'
import { normalizarSemaforo } from '../utils/filtrosMonitoramento'

const props = defineProps({
  value: { type: String, required: true },
  size: { type: String, default: 'small' },
  variant: { type: String, default: 'figma' },
  showIcon: { type: Boolean, default: true },
})

const resolved = computed(() => normalizarSemaforo(props.value))
</script>

<style scoped>
.figma-badge {
  margin-left: auto;
  font-size: 11px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 999px;
  white-space: nowrap;
}

.figma-badge--verde {
  background: rgba(34, 197, 94, 0.15);
  color: var(--green);
}

.figma-badge--amarelo {
  background: rgba(245, 158, 11, 0.15);
  color: var(--amber);
}

.figma-badge--vermelho {
  background: rgba(239, 68, 68, 0.15);
  color: var(--red);
}

.figma-badge--bloqueado,
.figma-badge--desconhecido {
  background: rgba(148, 163, 184, 0.15);
  color: var(--muted);
}
</style>
