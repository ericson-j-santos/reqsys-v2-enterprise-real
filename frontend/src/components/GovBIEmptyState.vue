<template>
  <GuidedEmptyState
    context="govbi-results"
    title="Nenhum resultado encontrado"
    description="A consulta foi processada, mas não retornou dados para os filtros informados. Revise a pergunta ou tente um exemplo sugerido."
    :reason="reason"
    action-label="Reformular pergunta"
    secondary-label="Executar novamente"
    icon="mdi-chart-box-outline"
    action-icon="mdi-pencil-outline"
    test-id="govbi-empty-state"
    @activate="$emit('reformulate')"
    @secondary="$emit('retry')"
  />
</template>

<script setup>
import GuidedEmptyState from './GuidedEmptyState.vue'

defineProps({ reason: { type: String, default: 'Não existem linhas compatíveis com a consulta atual.' } })
defineEmits(['reformulate', 'retry'])
</script>
