<template>
  <section class="service-case-page" data-testid="route-service-cases">
    <header class="page-header">
      <div>
        <p class="eyebrow">ReqSys Service Management</p>
        <h1>Caso de serviço</h1>
        <p class="muted">Uma única tela para REQUEST, INCIDENT, PROBLEM e CHANGE, sempre refletindo o estado persistido pelo backend.</p>
      </div>
    </header>

    <v-card class="pa-4 mb-4" variant="outlined">
      <form class="case-search" @submit.prevent="buscar">
        <v-text-field
          v-model="caseIdInput"
          label="Identificador do caso"
          placeholder="UUID do ServiceCase"
          autocomplete="off"
          hide-details="auto"
          :disabled="loading"
        />
        <v-btn type="submit" color="primary" prepend-icon="mdi-magnify" :loading="loading">Carregar caso</v-btn>
      </form>
    </v-card>

    <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4" data-testid="service-case-error">
      {{ errorMessage }}
    </v-alert>
    <v-alert v-if="successMessage" type="success" variant="tonal" class="mb-4" data-testid="service-case-success">
      {{ successMessage }}
    </v-alert>

    <template v-if="caseData">
      <div class="summary-grid mb-4">
        <v-card variant="outlined" class="pa-4">
          <div class="label">Tipo</div>
          <div class="value">{{ caseData.case_type }}</div>
        </v-card>
        <v-card variant="outlined" class="pa-4">
          <div class="label">Estado</div>
          <div class="value">{{ stateLabel(caseData.state) }}</div>
        </v-card>
        <v-card variant="outlined" class="pa-4">
          <div class="label">Prioridade</div>
          <div class="value">{{ caseData.priority }}</div>
        </v-card>
        <v-card variant="outlined" class="pa-4">
          <div class="label">Versão persistida</div>
          <div class="value">{{ caseData.version }}</div>
        </v-card>
      </div>

      <v-card variant="outlined" class="pa-4 mb-4">
        <div class="section-title">
          <div>
            <h2>Ações permitidas</h2>
            <p class="muted">A lista vem do domínio do backend. A tela não mantém uma segunda máquina de estados.</p>
          </div>
          <v-btn variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="carregar(caseData.case_id)">Atualizar</v-btn>
        </div>

        <div v-if="caseData.allowed_transitions?.length" class="actions-row">
          <v-btn
            v-for="target in caseData.allowed_transitions"
            :key="target"
            variant="tonal"
            color="primary"
            :loading="actionTarget === target"
            :disabled="loading || Boolean(actionTarget)"
            @click="executar(target)"
          >
            {{ actionLabel(target) }}
          </v-btn>
        </div>
        <v-alert v-else type="info" variant="tonal">Este caso não possui transições disponíveis no estado atual.</v-alert>

        <div v-if="caseData.allowed_transitions?.includes('RESOLVED')" class="evidence-grid mt-4">
          <v-text-field v-model="evidenceUri" label="URI da evidência de resolução" placeholder="urn:reqsys:evidence:..." hide-details="auto" />
          <v-text-field v-model="evidenceSha256" label="SHA-256 da evidência" placeholder="64 caracteres hexadecimais" hide-details="auto" />
        </div>
      </v-card>

      <div class="detail-grid">
        <v-card variant="outlined" class="pa-4">
          <h2>Dados do caso</h2>
          <dl class="details">
            <div><dt>ID</dt><dd class="mono">{{ caseData.case_id }}</dd></div>
            <div><dt>Solicitante</dt><dd>{{ caseData.requester }}</dd></div>
            <div><dt>Serviço</dt><dd class="mono">{{ caseData.service_id }}</dd></div>
            <div><dt>Impacto / urgência</dt><dd>{{ caseData.impact }} / {{ caseData.urgency }}</dd></div>
            <div><dt>Origem</dt><dd>{{ caseData.source }}</dd></div>
            <div><dt>Correlation ID</dt><dd class="mono">{{ caseData.correlation_id }}</dd></div>
          </dl>
        </v-card>

        <v-card variant="outlined" class="pa-4">
          <h2>Operação</h2>
          <dl class="details">
            <div><dt>Grupo atual</dt><dd>{{ operations?.current_assignment?.assignment_group || 'Não atribuído' }}</dd></div>
            <div><dt>Responsável</dt><dd>{{ operations?.current_assignment?.assignee || 'Não atribuído' }}</dd></div>
            <div><dt>SLA</dt><dd>{{ operations?.sla?.state || 'Não aplicado' }}</dd></div>
            <div><dt>Aprovações</dt><dd>{{ operations?.approvals?.length || 0 }}</dd></div>
          </dl>
        </v-card>
      </div>

      <v-card variant="outlined" class="pa-4 mt-4">
        <h2>Histórico auditável</h2>
        <v-table v-if="caseData.events?.length">
          <thead>
            <tr><th>Evento</th><th>De</th><th>Para</th><th>Correlation ID</th></tr>
          </thead>
          <tbody>
            <tr v-for="event in caseData.events" :key="event.event_id">
              <td>{{ event.event_type }}</td>
              <td>{{ event.from_state || '—' }}</td>
              <td>{{ event.to_state || '—' }}</td>
              <td class="mono">{{ event.correlation_id }}</td>
            </tr>
          </tbody>
        </v-table>
        <p v-else class="muted">Nenhum evento encontrado.</p>
      </v-card>
    </template>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../services/api'
import { carregarServiceCase, executarTransicaoServiceCase } from '../services/serviceCases'

const route = useRoute()
const router = useRouter()
const caseIdInput = ref('')
const caseData = ref(null)
const operations = ref(null)
const loading = ref(false)
const actionTarget = ref('')
const errorMessage = ref('')
const successMessage = ref('')
const evidenceUri = ref('')
const evidenceSha256 = ref('')

const STATE_LABELS = {
  NEW: 'Novo',
  TRIAGE: 'Triagem',
  PENDING_APPROVAL: 'Aguardando aprovação',
  IN_PROGRESS: 'Em andamento',
  PENDING_EXTERNAL: 'Aguardando dependência externa',
  RESOLVED: 'Resolvido',
  CLOSED: 'Fechado',
  CANCELED: 'Cancelado',
}
const ACTION_LABELS = {
  TRIAGE: 'Enviar para triagem',
  PENDING_APPROVAL: 'Solicitar aprovação',
  IN_PROGRESS: 'Iniciar / retomar',
  PENDING_EXTERNAL: 'Aguardar dependência externa',
  RESOLVED: 'Resolver',
  CLOSED: 'Fechar',
  CANCELED: 'Cancelar',
}

function stateLabel(value) { return STATE_LABELS[value] || value }
function actionLabel(value) { return ACTION_LABELS[value] || value }

async function carregar(rawCaseId) {
  errorMessage.value = ''
  successMessage.value = ''
  loading.value = true
  try {
    const result = await carregarServiceCase(api, rawCaseId)
    caseData.value = result.caseData
    operations.value = result.operations
    caseIdInput.value = result.caseData.case_id
    evidenceUri.value = ''
    evidenceSha256.value = ''
  } catch (error) {
    caseData.value = null
    operations.value = null
    errorMessage.value = error?.response?.data?.detail || error?.message || 'Não foi possível carregar o caso.'
  } finally {
    loading.value = false
  }
}

async function buscar() {
  const id = caseIdInput.value.trim()
  if (!id) {
    errorMessage.value = 'Informe o identificador do caso.'
    return
  }
  await router.push({ name: 'service-case', params: { caseId: id } })
}

async function executar(target) {
  errorMessage.value = ''
  successMessage.value = ''
  actionTarget.value = target
  try {
    const result = await executarTransicaoServiceCase(api, caseData.value, target, {
      evidenceUri: evidenceUri.value,
      evidenceSha256: evidenceSha256.value,
    })
    caseData.value = result.caseData
    operations.value = result.operations
    successMessage.value = result.duplicate
      ? 'A ação já havia sido aplicada; a leitura persistida confirmou o mesmo estado.'
      : 'Ação aplicada e confirmada por leitura independente do estado persistido.'
    evidenceUri.value = ''
    evidenceSha256.value = ''
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || 'A ação foi recusada.'
    // Releitura fail-safe após erro: evita manter estado visual otimista ou obsoleto.
    try {
      const fresh = await carregarServiceCase(api, caseData.value.case_id)
      caseData.value = fresh.caseData
      operations.value = fresh.operations
    } catch {
      // O erro original permanece visível; não substituímos por falsa confirmação.
    }
  } finally {
    actionTarget.value = ''
  }
}

watch(() => route.params.caseId, async (caseId) => {
  if (caseId && caseId !== caseData.value?.case_id) await carregar(caseId)
})

onMounted(async () => {
  if (route.params.caseId) {
    caseIdInput.value = String(route.params.caseId)
    await carregar(route.params.caseId)
  }
})
</script>

<style scoped>
.service-case-page { padding: var(--space-xl); max-width: 1440px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; gap: var(--space-lg); margin-bottom: var(--space-lg); }
.eyebrow { color: var(--amber); font-weight: 800; margin-bottom: var(--space-xs); }
h1 { font-size: clamp(1.8rem, 3vw, 2.5rem); }
h2 { font-size: var(--font-size-lg); margin-bottom: var(--space-sm); }
.case-search { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-md); align-items: start; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-md); }
.detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-md); }
.evidence-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-md); }
.section-title { display: flex; justify-content: space-between; gap: var(--space-md); align-items: start; }
.actions-row { display: flex; flex-wrap: wrap; gap: var(--space-sm); }
.label, dt { color: var(--muted); font-size: var(--font-size-sm); }
.value { font-size: var(--font-size-xl); font-weight: 800; margin-top: var(--space-xs); }
.details { display: grid; gap: var(--space-sm); }
.details > div { display: grid; grid-template-columns: minmax(120px, .45fr) 1fr; gap: var(--space-md); }
dd { margin: 0; overflow-wrap: anywhere; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: var(--font-size-sm); }
.muted { color: var(--muted); }
@media (max-width: 900px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .detail-grid, .evidence-grid { grid-template-columns: 1fr; }
}
@media (max-width: 600px) {
  .service-case-page { padding: var(--space-md); }
  .case-search, .summary-grid { grid-template-columns: 1fr; }
  .section-title { flex-direction: column; }
}
</style>
