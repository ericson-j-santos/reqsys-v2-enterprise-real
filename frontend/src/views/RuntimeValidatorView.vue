<template>
  <section>
    <PageHeader title="Runtime Validator" subtitle="Health, score operacional, incidentes, remediação e evidências governadas." />
    <v-row>
      <v-col cols="12" md="4">
        <v-card class="pa-4" variant="tonal">
          <div class="text-caption">Stability Score</div>
          <div class="text-h3 font-weight-bold">{{ dashboard?.stability_score ?? '—' }}</div>
          <v-chip :color="statusColor" class="mt-2">{{ dashboard?.status || 'carregando' }}</v-chip>
        </v-card>
      </v-col>
      <v-col cols="12" md="8">
        <v-card class="pa-4">
          <div class="text-h6 mb-3">Runtime Health</div>
          <v-list density="compact">
            <v-list-item v-for="check in dashboard?.checks || []" :key="check.name" :title="check.name" :subtitle="check.message">
              <template #append><v-chip size="small" :color="check.status === 'healthy' ? 'green' : 'amber'">{{ check.status }}</v-chip></template>
            </v-list-item>
          </v-list>
        </v-card>
      </v-col>
      <v-col cols="12" md="6">
        <v-card class="pa-4">
          <div class="text-h6 mb-3">Validação de Workflow</div>
          <v-btn color="primary" @click="validar">Validar CI exemplo</v-btn>
          <pre class="mt-3 runtime-json">{{ workflowResult }}</pre>
        </v-card>
      </v-col>
      <v-col cols="12" md="6">
        <v-card class="pa-4">
          <div class="text-h6 mb-3">Auto-Remediation segura</div>
          <v-btn color="warning" @click="remediar">Simular rerun governado</v-btn>
          <pre class="mt-3 runtime-json">{{ remediationResult }}</pre>
        </v-card>
      </v-col>
      <v-col cols="12">
        <v-card class="pa-4">
          <div class="text-h6 mb-3">Runtime Timeline</div>
          <v-timeline side="end" density="compact">
            <v-timeline-item v-for="event in dashboard?.timeline || []" :key="event.id" dot-color="primary" size="small">
              <strong>{{ event.title }}</strong><div class="text-caption">{{ event.event_type }} · {{ event.correlation_id }}</div>
            </v-timeline-item>
          </v-timeline>
        </v-card>
      </v-col>
    </v-row>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import { carregarRuntimeDashboard, solicitarRemediacao, validarWorkflow } from '../services/runtimeValidator'

const dashboard = ref(null)
const workflowResult = ref('')
const remediationResult = ref('')
const statusColor = computed(() => dashboard.value?.status === 'healthy' ? 'green' : dashboard.value?.status === 'degraded' ? 'amber' : 'red')

async function carregar() { dashboard.value = await carregarRuntimeDashboard() }
async function validar() {
  workflowResult.value = JSON.stringify(await validarWorkflow({ workflow_name: 'CI — ReqSys v2 Enterprise', required_jobs: ['backend', 'frontend', 'e2e'], completed_jobs: ['backend', 'frontend'], failed_jobs: [], evidence_urls: ['artifact://runtime-evidence'] }), null, 2)
}
async function remediar() {
  remediationResult.value = JSON.stringify(await solicitarRemediacao({ target: 'CI — ReqSys v2 Enterprise', action: 'rerun_workflow', mode: 'dry_run', max_retries: 2 }), null, 2)
  await carregar()
}
onMounted(carregar)
</script>

<style scoped>
.runtime-json { white-space: pre-wrap; font-size: 12px; background: #0f172a; color: #d1fae5; padding: 12px; border-radius: 8px; }
</style>
