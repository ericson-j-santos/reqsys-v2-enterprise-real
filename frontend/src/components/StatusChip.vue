<!--
  StatusChip — componente padrão para exibição de status/origem com mapeamento de cores.

  Props:
    value     (String, obrigatório) — valor do status/origem
    map       (Object) — mapeamento customizado { valor: { label, color } }
                         Substitui o mapa padrão se fornecido.
    tooltip   (String) — texto do tooltip (opcional)
    size      (String) — tamanho Vuetify (padrão: 'small')
    variant   (String) — variante Vuetify (padrão: 'tonal')

  Mapa padrão (status de requisito / origem de segredo):
    pendente  → amber
    aprovado  → green
    rejeitado → red
    em analise → blue
    concluido → teal
    env       → amber   (Ambiente)
    vault     → green   (Cofre)
    default   → blue    (Default)
    absent    → grey    (Ausente)

  Exemplos:
    <StatusChip value="pendente" />
    <StatusChip value="vault" tooltip="Lido do cofre de segredos" />
    <StatusChip value="aprovado" :map="{ aprovado: { label: 'OK', color: 'green' } }" />
-->
<template>
  <v-tooltip v-if="tooltip" :text="tooltip" location="top">
    <template #activator="{ props }">
      <v-chip v-bind="props" :size="size" :color="resolved.color" :variant="variant">
        {{ resolved.label }}
      </v-chip>
    </template>
  </v-tooltip>
  <v-chip v-else :size="size" :color="resolved.color" :variant="variant">
    {{ resolved.label }}
  </v-chip>
</template>

<script setup>
import { computed } from 'vue'

const DEFAULT_MAP = {
  // Status de requisito
  pendente:    { label: 'Pendente',    color: 'amber' },
  aprovado:    { label: 'Aprovado',    color: 'green' },
  rejeitado:   { label: 'Rejeitado',  color: 'red' },
  'em analise':{ label: 'Em Análise', color: 'blue' },
  concluido:   { label: 'Concluído',  color: 'teal' },
  cancelado:   { label: 'Cancelado',  color: 'grey' },

  // Origem de segredo
  env:     { label: 'Ambiente', color: 'amber' },
  vault:   { label: 'Cofre',   color: 'green' },
  default: { label: 'Default', color: 'blue'  },
  absent:  { label: 'Ausente', color: 'grey'  },

  // Pipeline
  success:  { label: 'Sucesso',    color: 'green' },
  failed:   { label: 'Falhou',     color: 'red' },
  running:  { label: 'Executando', color: 'blue' },
  skipped:  { label: 'Pulado',     color: 'grey' },
}

const props = defineProps({
  value:   { type: String, required: true },
  map:     { type: Object, default: null },
  tooltip: { type: String, default: '' },
  size:    { type: String, default: 'small' },
  variant: { type: String, default: 'tonal' },
})

const resolved = computed(() => {
  const key = (props.value || '').toLowerCase()
  const merged = props.map ? { ...DEFAULT_MAP, ...props.map } : DEFAULT_MAP
  return merged[key] || { label: props.value, color: 'grey' }
})
</script>
