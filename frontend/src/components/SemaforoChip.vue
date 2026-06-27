<!--
  SemaforoChip — semáforo operacional canônico (verde / amarelo / vermelho / bloqueado).

  Props:
    value   (String, obrigatório) — estado operacional
    size    (String) — tamanho Vuetify (padrão: 'small')
    variant (String) — variante Vuetify (padrão: 'tonal')
    showIcon (Boolean) — exibe ícone do semáforo (padrão: true)
-->
<template>
  <v-chip :size="size" :color="resolved.color" :variant="variant" :data-testid="`semaforo-${resolved.key}`">
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
  variant: { type: String, default: 'tonal' },
  showIcon: { type: Boolean, default: true },
})

const resolved = computed(() => normalizarSemaforo(props.value))
</script>
