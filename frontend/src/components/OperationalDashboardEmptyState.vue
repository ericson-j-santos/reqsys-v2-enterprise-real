<template>
  <GuidedEmptyState
    :context="context"
    title="Ainda não há dados para exibir"
    description="O painel está disponível, mas não recebeu informações compatíveis com o período ou filtros atuais."
    :reason="reason"
    action-label="Atualizar dados"
    secondary-label="Limpar filtros"
    icon="mdi-view-dashboard-outline"
    test-id="operational-dashboard-empty-state"
    @activate="$emit('refresh')"
    @secondary="$emit('clear-filters')"
  />
</template>

<script setup>
import GuidedEmptyState from './GuidedEmptyState.vue'

defineProps({
  context: { type: String, default: 'operational-dashboard' },
  reason: { type: String, default: 'Nenhum registro atende aos filtros selecionados.' },
})
defineEmits(['refresh', 'clear-filters'])
</script>
