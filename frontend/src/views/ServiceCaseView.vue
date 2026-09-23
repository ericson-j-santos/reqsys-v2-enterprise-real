<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../services/api'

const route = useRoute()
const router = useRouter()

const caseId = ref(String(route.params.caseId || ''))
const serviceCase = ref(null)
const carregando = ref(false)
const alterando = ref('')
const erro = ref('')
const sucesso = ref('')
const evidenceUri = ref('')
const evidenceSha256 = ref('')

const transicoesPermitidas = computed(() => serviceCase.value?.allowed_transitions || [])
const exigeEvidenciaResolucao = computed(() => transicoesPermitidas.value.includes('RESOLVED'))

const rotulosEstado = {
  NEW: 'Novo',
  TRIAGE: 'Triagem',
  PENDING_APPROVAL: 'Aguardando aprovação',
  IN_PROGRESS: 'Em andamento',
  PENDING_EXTERNAL: 'Aguardando externo',
  RESOLVED: 'Resolvido',
  CLOSED: 'Fechado',
  CANCELED: 'Cancelado',
}

function rotuloEstado(value) {
  return rotulosEstado[value] || value
}

function detalheErro(error) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  return 'Não foi possível concluir a operação. O estado persistido foi relido sem assumir sucesso.'
}

function novoEventId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `ui-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

async function buscarCaso({ preservarMensagens = false } = {}) {
  const id = caseId.value.trim()
  if (!id) {
    erro.value = 'Informe o identificador do ServiceCase.'
    return
  }

  carregando.value = true
  if (!preservarMensagens) {
    erro.value = ''
    sucesso.value = ''
  }
  try {
    const response = await api.get(`/v1/service-cases/${encodeURIComponent(id)}`)
    serviceCase.value = response.data.data
    caseId.value = serviceCase.value.case_id
    if (route.params.caseId !== serviceCase.value.case_id) {
      await router.replace({
        path: `/service-cases/${encodeURIComponent(serviceCase.value.case_id)}`,
      })
    }
  } catch (error) {
    serviceCase.value = null
    erro.value = detalheErro(error)
  } finally {
    carregando.value = false
  }
}

async function transicionar(targetState) {
  if (!serviceCase.value || alterando.value) return

  if (targetState === 'RESOLVED') {
    if (!evidenceUri.value.trim() || !/^[a-f0-9]{64}$/.test(evidenceSha256.value.trim())) {
      erro.value = 'A resolução exige URI de evidência e SHA-256 hexadecimal com 64 caracteres.'
      sucesso.value = ''
      return
    }
  }

  alterando.value = targetState
  erro.value = ''
  sucesso.value = ''
  const beforeState = serviceCase.value.state

  const payload = {
    target_state: targetState,
    expected_version: serviceCase.value.version,
    event_id: novoEventId(),
  }
  if (targetState === 'RESOLVED') {
    payload.evidence_uri = evidenceUri.value.trim()
    payload.evidence_sha256 = evidenceSha256.value.trim()
  }

  try {
    await api.post(
      `/v1/service-cases/${encodeURIComponent(serviceCase.value.case_id)}/transitions`,
      payload,
    )
    await buscarCaso({ preservarMensagens: true })
    if (serviceCase.value?.state !== targetState) {
      throw new Error('estado_persistido_divergente')
    }
    sucesso.value = `Estado persistido confirmado: ${rotuloEstado(beforeState)} → ${rotuloEstado(targetState)}.`
    if (targetState === 'RESOLVED') {
      evidenceUri.value = ''
      evidenceSha256.value = ''
    }
  } catch (error) {
    // Nunca materializar a resposta da mutação como verdade local. Relê a API
    // autoritativa inclusive no caminho de erro para impedir falso sucesso.
    await buscarCaso({ preservarMensagens: true })
    erro.value = detalheErro(error)
    sucesso.value = ''
  } finally {
    alterando.value = ''
  }
}

onMounted(() => {
  if (caseId.value.trim()) buscarCaso()
})
</script>

<template>
  <div class="pa-4 service-case-view" data-testid="service-case-view">
    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-4">
      <div>
        <h1 class="text-h4 font-weight-bold">ServiceCase</h1>
        <p class="text-body-2 text-medium-emphasis mb-0">
          Tela única para REQUEST, INCIDENT, PROBLEM e CHANGE. As ações disponíveis vêm do backend.
        </p>
      </div>
      <v-chip v-if="serviceCase" color="primary" variant="tonal">
        {{ serviceCase.case_type }}
      </v-chip>
    </div>

    <v-card variant="outlined" class="mb-4">
      <v-card-text>
        <div class="d-flex flex-column flex-md-row ga-2">
          <v-text-field
            v-model="caseId"
            label="Identificador do ServiceCase"
            variant="outlined"
            density="compact"
            hide-details="auto"
            data-testid="service-case-id"
            @keyup.enter="buscarCaso()"
          />
          <v-btn
            color="primary"
            :loading="carregando"
            data-testid="service-case-load"
            @click="buscarCaso()"
          >
            Carregar
          </v-btn>
        </div>
      </v-card-text>
    </v-card>

    <v-alert
      v-if="erro"
      type="error"
      variant="tonal"
      class="mb-4"
      data-testid="service-case-error"
    >
      {{ erro }}
    </v-alert>

    <v-alert
      v-if="sucesso"
      type="success"
      variant="tonal"
      class="mb-4"
      data-testid="service-case-success"
    >
      {{ sucesso }}
    </v-alert>

    <v-card v-if="serviceCase" variant="outlined" data-testid="service-case-card">
      <v-card-title class="d-flex flex-wrap align-center ga-2">
        <span>{{ serviceCase.case_id }}</span>
        <v-chip size="small" color="secondary" variant="tonal" data-testid="service-case-state">
          {{ rotuloEstado(serviceCase.state) }}
        </v-chip>
        <v-chip size="small" variant="outlined">v{{ serviceCase.version }}</v-chip>
      </v-card-title>

      <v-card-text>
        <v-row dense>
          <v-col cols="12" md="6"><strong>Solicitante:</strong> {{ serviceCase.requester }}</v-col>
          <v-col cols="12" md="6"><strong>Serviço:</strong> {{ serviceCase.service_id }}</v-col>
          <v-col cols="12" md="4"><strong>Prioridade:</strong> {{ serviceCase.priority }}</v-col>
          <v-col cols="12" md="4"><strong>Impacto:</strong> {{ serviceCase.impact }}</v-col>
          <v-col cols="12" md="4"><strong>Urgência:</strong> {{ serviceCase.urgency }}</v-col>
          <v-col cols="12"><strong>Correlation ID:</strong> {{ serviceCase.correlation_id }}</v-col>
        </v-row>

        <v-divider class="my-4" />

        <h2 class="text-subtitle-1 font-weight-bold mb-2">Ações permitidas pelo backend</h2>
        <div
          v-if="transicoesPermitidas.length"
          class="d-flex flex-wrap ga-2"
          data-testid="service-case-actions"
        >
          <v-btn
            v-for="target in transicoesPermitidas"
            :key="target"
            size="small"
            variant="tonal"
            :loading="alterando === target"
            :disabled="Boolean(alterando)"
            :data-testid="`transition-${target}`"
            @click="transicionar(target)"
          >
            {{ rotuloEstado(target) }}
          </v-btn>
        </div>
        <v-alert v-else type="info" variant="tonal" density="compact">
          Este caso não possui transições de estado disponíveis.
        </v-alert>

        <div v-if="exigeEvidenciaResolucao" class="mt-4" data-testid="resolution-evidence">
          <h3 class="text-subtitle-2 font-weight-bold mb-2">Evidência exigida para resolução</h3>
          <v-text-field
            v-model="evidenceUri"
            label="URI da evidência"
            variant="outlined"
            density="compact"
            hide-details="auto"
            class="mb-2"
          />
          <v-text-field
            v-model="evidenceSha256"
            label="SHA-256 da evidência"
            variant="outlined"
            density="compact"
            hide-details="auto"
          />
        </div>

        <v-divider class="my-4" />

        <h2 class="text-subtitle-1 font-weight-bold mb-2">Histórico persistido</h2>
        <v-table density="compact">
          <thead>
            <tr>
              <th>Evento</th>
              <th>Origem</th>
              <th>Destino</th>
              <th>Correlation ID</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in serviceCase.events || []" :key="event.event_id">
              <td>{{ event.event_type }}</td>
              <td>{{ event.from_state || '—' }}</td>
              <td>{{ event.to_state || '—' }}</td>
              <td>{{ event.correlation_id }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>
  </div>
</template>
