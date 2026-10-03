<template>
  <section
    class="guided-empty-state"
    role="status"
    aria-live="polite"
    :aria-labelledby="titleId"
    :data-testid="testId"
  >
    <v-icon :icon="icon" size="56" color="primary" aria-hidden="true" />
    <h2 :id="titleId" class="text-h6 mt-3 mb-2">{{ title }}</h2>
    <p class="text-body-2 text-medium-emphasis mb-4">{{ description }}</p>
    <p v-if="reason" class="text-caption text-medium-emphasis mb-4">
      <strong>Motivo:</strong> {{ reason }}
    </p>
    <div class="d-flex flex-wrap justify-center gap-2">
      <v-btn
        color="primary"
        :prepend-icon="actionIcon"
        :data-testid="`${testId}-primary-action`"
        @click="activate"
      >
        {{ actionLabel }}
      </v-btn>
      <v-btn
        v-if="secondaryLabel"
        variant="tonal"
        :data-testid="`${testId}-secondary-action`"
        @click="secondary"
      >
        {{ secondaryLabel }}
      </v-btn>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { recordEmptyState } from '../services/emptyStateTelemetry'

const props = defineProps({
  context: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true },
  reason: { type: String, default: '' },
  actionLabel: { type: String, required: true },
  secondaryLabel: { type: String, default: '' },
  icon: { type: String, default: 'mdi-database-off-outline' },
  actionIcon: { type: String, default: 'mdi-refresh' },
  testId: { type: String, default: 'guided-empty-state' },
})
const emit = defineEmits(['activate', 'secondary'])
const titleId = computed(() => `${props.testId}-title`)

function activate() {
  recordEmptyState({ context: props.context, event: 'primary_action' })
  emit('activate')
}
function secondary() {
  recordEmptyState({ context: props.context, event: 'secondary_action' })
  emit('secondary')
}
onMounted(() => recordEmptyState({ context: props.context, event: 'view' }))
</script>

<style scoped>
.guided-empty-state {
  display: grid;
  justify-items: center;
  text-align: center;
  padding: clamp(24px, 5vw, 48px);
  border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 18px;
}
.guided-empty-state p { max-width: 60ch; }
</style>
