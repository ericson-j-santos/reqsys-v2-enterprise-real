<template>
  <section v-if="config" class="auth-diagnostics" data-testid="auth-diagnostics-panel">
    <v-alert
      v-if="resumo.divergente"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-3"
      data-testid="auth-redirect-warning"
    >
      <div class="font-weight-medium">Redirect URI divergente</div>
      <div class="text-caption mt-1">
        Esta pagina usa <strong>{{ resumo.atual }}</strong>
        <span v-if="resumo.esperado">
          , mas a API espera <strong>{{ resumo.esperado }}</strong>
        </span>.
      </div>
      <div class="text-caption mt-1">
        Acesse pela URL canonica do ambiente ou registre a origem atual no Microsoft Entra ID.
      </div>
    </v-alert>

    <v-alert
      type="info"
      variant="tonal"
      density="compact"
      class="mb-3"
      data-testid="auth-redirect-validation"
    >
      <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-1">
        <span class="font-weight-medium">Diagnostico Microsoft Entra ID</span>
        <v-chip
          size="x-small"
          :color="chipCor"
          variant="tonal"
          data-testid="auth-diagnostics-status-chip"
        >
          {{ chipRotulo }}
        </v-chip>
      </div>

      <div class="text-caption">
        Ambiente: <strong>{{ resumo.ambienteLabel }}</strong>
      </div>
      <div class="text-caption mt-1">
        Redirect URI desta sessao: <strong>{{ resumo.atual }}</strong>
      </div>
      <div v-if="resumo.esperado" class="text-caption">
        Redirect URI esperado pela API: <strong>{{ resumo.esperado }}</strong>
      </div>
      <div class="text-caption mt-1">
        Azure AD: {{ resumo.azureEnabled ? 'habilitado' : 'nao configurado' }}
        · Status: {{ resumo.authStatus }}
      </div>

      <div v-if="camposAusentes.length" class="text-caption mt-1">
        Campos ausentes: {{ camposAusentes.join(', ') }}
      </div>
      <div v-if="operatorAction && !resumo.azureEnabled" class="text-caption mt-1">
        {{ operatorAction }}
      </div>

      <div v-if="resumo.divergenteEsperado && !resumo.divergente" class="text-caption mt-1">
        A origem atual e canonica, mas difere do redirect principal declarado pela API.
      </div>

      <div v-if="resumo.canonicalUris.length" class="text-caption mt-2">
        Origens canonicas deste ambiente (registrar no Entra ID):
      </div>
      <ul v-if="resumo.canonicalUris.length" class="auth-diagnostics-list text-caption">
        <li v-for="uri in resumo.canonicalUris" :key="uri">
          <code>{{ uri }}</code>
        </li>
      </ul>

      <div v-if="resumo.hint" class="text-caption mt-2">
        {{ resumo.hint }}
      </div>
    </v-alert>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { resumoValidacaoAuth } from '../auth/diagnostics'

const props = defineProps({
  config: { type: Object, default: null },
})

const resumo = computed(() => resumoValidacaoAuth(props.config))
const camposAusentes = computed(() => props.config?.missing_fields || [])
const operatorAction = computed(() => props.config?.operator_action || '')

const chipCor = computed(() => {
  if (!resumo.value.azureEnabled) return 'warning'
  if (resumo.value.divergente) return 'warning'
  if (resumo.value.azurePronto && resumo.value.alinhado) return 'success'
  return 'info'
})

const chipRotulo = computed(() => {
  if (!resumo.value.azureEnabled) return 'configuracao incompleta'
  if (resumo.value.divergente) return 'redirect divergente'
  if (resumo.value.azurePronto && resumo.value.alinhado) return 'pronto para login'
  return 'verificar configuracao'
})
</script>

<style scoped>
.auth-diagnostics-list {
  margin: 4px 0 0;
  padding-left: 18px;
}

.auth-diagnostics-list code {
  font-size: 0.75rem;
  word-break: break-all;
}
</style>
