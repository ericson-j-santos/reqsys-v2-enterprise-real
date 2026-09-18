<template>
  <v-container fluid class="pa-4" data-testid="route-session-management">
    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-4">
      <div>
        <h1 class="text-h5 font-weight-bold">Gerenciamento de sessões</h1>
        <p class="text-body-2 text-medium-emphasis mb-0">
          Atualização de permissões e invalidação governada de sessões humanas do ReqSys.
        </p>
      </div>
      <v-chip :color="status.production_touched ? 'error' : 'success'" variant="tonal">
        {{ status.production_touched ? 'Produção' : 'Ambiente não produtivo' }}
      </v-chip>
    </div>

    <v-alert type="info" variant="tonal" class="mb-4">
      Tokens e segredos não são exibidos. O controle usa <strong>session epoch</strong> para revogação global
      e <strong>authz version</strong> para detectar alterações de RBAC.
    </v-alert>

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4">{{ erro }}</v-alert>
    <v-alert v-if="mensagem" type="success" variant="tonal" class="mb-4">{{ mensagem }}</v-alert>

    <v-progress-linear v-if="carregando" indeterminate class="mb-4" />

    <v-row>
      <v-col cols="12" md="6">
        <v-card variant="outlined" height="100%">
          <v-card-title>Minha sessão</v-card-title>
          <v-card-text>
            <p class="text-body-2 mb-4">
              Recarrega permissões atuais e emite um novo token sem alterar a identidade autenticada.
            </p>
            <div class="d-flex flex-wrap ga-2">
              <v-btn color="primary" :loading="atualizando" @click="atualizarSessao">
                Atualizar permissões
              </v-btn>
              <v-btn variant="outlined" color="warning" @click="resetarSessaoLocal">
                Resetar sessão e autenticar novamente
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card variant="outlined" height="100%">
          <v-card-title>Estado de segurança</v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item title="Ambiente" :subtitle="status.environment || '—'" />
              <v-list-item title="Session epoch" :subtitle="String(status.session_epoch ?? '—')" />
              <v-list-item title="Authz version" :subtitle="status.authz_version || '—'" />
              <v-list-item title="Última invalidação" :subtitle="formatarData(status.invalidated_at)" />
              <v-list-item title="Executada por" :subtitle="status.invalidated_by || '—'" />
              <v-list-item title="Correlation ID" :subtitle="status.correlation_id || '—'" />
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card variant="outlined" class="mt-4">
      <v-card-title>Reset forçado de segurança</v-card-title>
      <v-card-text>
        <v-alert type="warning" variant="tonal" class="mb-4">
          Esta ação incrementa o <strong>session epoch</strong> e invalida todos os JWTs humanos emitidos anteriormente.
          Tokens de serviço escopados não são rotacionados nem revogados por esta operação.
        </v-alert>
        <v-textarea
          v-model.trim="motivo"
          label="Motivo da invalidação"
          rows="2"
          maxlength="1000"
          counter
          placeholder="Ex.: alteração de RBAC ou resposta a incidente de segurança"
        />
        <v-text-field
          v-model.trim="confirmacao"
          label="Confirmação obrigatória"
          :hint="`Digite exatamente: ${status.required_confirmation || 'carregando...'}`"
          persistent-hint
          autocomplete="off"
          class="mb-3"
        />
        <v-btn
          color="error"
          :loading="invalidando"
          :disabled="!podeInvalidar"
          @click="invalidarTodas"
        >
          Invalidar todas as sessões
        </v-btn>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  carregarStatusSessoes,
  invalidarTodasSessoes,
  mensagemErroSessao,
} from '../services/sessionManagement'

const router = useRouter()
const auth = useAuthStore()
const status = ref({})
const erro = ref('')
const mensagem = ref('')
const carregando = ref(false)
const atualizando = ref(false)
const invalidando = ref(false)
const confirmacao = ref('')
const motivo = ref('')

const podeInvalidar = computed(() => Boolean(
  status.value.required_confirmation &&
  confirmacao.value === status.value.required_confirmation &&
  motivo.value.trim().length >= 8,
))

function formatarData(value) {
  if (!value) return 'Nunca executado'
  try { return new Date(value).toLocaleString('pt-BR') } catch { return value }
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    status.value = await carregarStatusSessoes()
  } catch (e) {
    erro.value = mensagemErroSessao(e)
  } finally {
    carregando.value = false
  }
}

async function atualizarSessao() {
  atualizando.value = true
  erro.value = ''
  mensagem.value = ''
  try {
    await auth.atualizarSessao()
    mensagem.value = 'Sessão atualizada com as permissões vigentes.'
    await carregar()
  } catch (e) {
    erro.value = mensagemErroSessao(e)
  } finally {
    atualizando.value = false
  }
}

function resetarSessaoLocal() {
  auth.sair()
  router.replace({ path: '/login', query: { redirect: '/admin/session-management', reset: 'security' } })
}

async function invalidarTodas() {
  invalidando.value = true
  erro.value = ''
  mensagem.value = ''
  try {
    await invalidarTodasSessoes(confirmacao.value, motivo.value)
    auth.sair()
    await router.replace({ path: '/login', query: { redirect: '/admin/session-management', reset: 'global' } })
  } catch (e) {
    erro.value = mensagemErroSessao(e)
  } finally {
    invalidando.value = false
  }
}

onMounted(carregar)
</script>
