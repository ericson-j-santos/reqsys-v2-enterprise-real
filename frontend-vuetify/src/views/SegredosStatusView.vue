<template>
  <div class="secrets-page">
    <div class="page-header">
      <div>
        <div class="text-h5 font-weight-bold mb-1">Status de Segredos</div>
        <div class="text-body-2 text-medium-emphasis">
          Diagnóstico da origem dos segredos do backend, sem exposição de valores.
        </div>
      </div>

      <div class="page-actions">
        <v-btn variant="outlined" prepend-icon="mdi-lock-plus-outline" color="success" @click="dialogGravar = true">
          Gravar segredo
        </v-btn>
        <v-btn variant="outlined" prepend-icon="mdi-cog-play-outline" color="secondary" :loading="initLoading" @click="inicializarVault">
          Inicializar vault
        </v-btn>
        <v-btn variant="outlined" prepend-icon="mdi-refresh" :loading="loading" @click="loadSecrets">
          Atualizar
        </v-btn>
        <v-chip :color="statusColor" variant="tonal" prepend-icon="mdi-shield-key-outline">
          {{ statusLabel }}
        </v-chip>
      </div>
    </div>

    <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4" closable @click:close="errorMessage = ''">
      {{ errorMessage }}
    </v-alert>
    <v-alert v-if="successMessage" type="success" variant="tonal" class="mb-4" closable @click:close="successMessage = ''">
      {{ successMessage }}
    </v-alert>

    <v-row>
      <v-col cols="12" md="4">
        <v-card rounded="xl" elevation="1" class="panel-card h-100">
          <v-card-title>Resumo</v-card-title>
          <v-divider />
          <v-card-text>
            <v-row>
              <v-col cols="6" md="12" xl="6">
                <div class="summary-item">
                  <div class="summary-label">Total monitorado</div>
                  <div class="summary-value">{{ total }}</div>
                </div>
              </v-col>
              <v-col cols="6" md="12" xl="6">
                <div class="summary-item">
                  <div class="summary-label">Via ambiente</div>
                  <div class="summary-value">{{ countBySource.env }}</div>
                </div>
              </v-col>
              <v-col cols="6" md="12" xl="6">
                <div class="summary-item">
                  <div class="summary-label">Via cofre</div>
                  <div class="summary-value is-good">{{ countBySource.vault }}</div>
                </div>
              </v-col>
              <v-col cols="6" md="12" xl="6">
                <div class="summary-item">
                  <div class="summary-label">Usando default</div>
                  <div class="summary-value is-warning">{{ countBySource.default }}</div>
                </div>
              </v-col>
            </v-row>

            <v-alert type="info" variant="tonal" density="comfortable" class="mt-2">
              A API retorna apenas a origem da configuração. Os valores reais dos segredos não são expostos.
            </v-alert>

            <v-alert v-if="countBySource.default > 0" type="warning" variant="tonal" density="comfortable" class="mt-3">
              {{ countBySource.default }} segredo(s) ainda usam valor padrão.
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="8">
        <v-card rounded="xl" elevation="1" class="panel-card">
          <v-card-title class="d-flex align-center justify-space-between ga-2 flex-wrap">
            <span>Segredos monitorados</span>
            <v-chip size="small" color="secondary" variant="tonal">{{ secrets.length }}</v-chip>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-0">
            <v-table density="comfortable" hover>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Origem</th>
                  <th>Resolvido</th>
                  <th>Cofre / Serviço</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="secret in secrets" :key="secret.name">
                  <td>
                    <div class="font-weight-medium">{{ secret.name }}</div>
                    <div class="text-caption text-medium-emphasis">env: {{ secret.env_name || secret.name }}</div>
                  </td>
                  <td>
                    <v-chip size="small" :color="sourceColor(secret.source)" variant="tonal">
                      {{ sourceLabel(secret.source) }}
                    </v-chip>
                  </td>
                  <td>
                    <v-icon :color="secret.resolved ? 'success' : 'warning'">
                      {{ secret.resolved ? 'mdi-check-circle' : 'mdi-alert-circle-outline' }}
                    </v-icon>
                  </td>
                  <td>
                    <span v-if="secret.vault_key" class="text-caption">
                      <strong>{{ secret.vault_key }}</strong>
                      <span v-if="secret.vault_service_name" class="text-medium-emphasis"> · {{ secret.vault_service_name }}</span>
                    </span>
                    <span v-else class="text-medium-emphasis">—</span>
                  </td>
                  <td>
                    <div class="d-flex ga-1 justify-end">
                      <v-btn
                        icon="mdi-pencil-outline"
                        size="x-small"
                        variant="text"
                        color="primary"
                        title="Gravar no cofre"
                        @click="abrirGravar(secret.name)"
                      />
                      <v-btn
                        v-if="secret.source === 'vault'"
                        icon="mdi-delete-outline"
                        size="x-small"
                        variant="text"
                        color="error"
                        title="Remover do cofre"
                        :loading="deletingKey === secret.name"
                        @click="confirmarRemocao(secret.name)"
                      />
                    </div>
                  </td>
                </tr>
                <tr v-if="!secrets.length && !loading">
                  <td colspan="5" class="empty-cell">Nenhum diagnóstico retornado.</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Dialog: gravar segredo -->
    <v-dialog v-model="dialogGravar" max-width="500" persistent>
      <v-card rounded="xl">
        <v-card-title class="pt-5 px-6">Gravar segredo no cofre</v-card-title>
        <v-card-text class="px-6">
          <v-text-field
            v-model="form.key"
            label="Chave (ex: JWT_SECRET)"
            variant="outlined"
            density="compact"
            class="mb-3"
            :error-messages="formErrors.key"
          />
          <v-text-field
            v-model="form.value"
            label="Valor"
            variant="outlined"
            density="compact"
            :type="showValue ? 'text' : 'password'"
            :append-inner-icon="showValue ? 'mdi-eye-off' : 'mdi-eye'"
            @click:append-inner="showValue = !showValue"
            :error-messages="formErrors.value"
          />
          <v-alert v-if="formError" type="error" variant="tonal" density="compact" class="mt-2">
            {{ formError }}
          </v-alert>
        </v-card-text>
        <v-card-actions class="px-6 pb-5 ga-2">
          <v-spacer />
          <v-btn variant="text" @click="fecharGravar">Cancelar</v-btn>
          <v-btn color="success" variant="flat" :loading="saveLoading" @click="gravarSegredo">Gravar</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Dialog: confirmar remoção -->
    <v-dialog v-model="dialogRemover" max-width="420">
      <v-card rounded="xl">
        <v-card-title class="pt-5 px-6">Remover segredo</v-card-title>
        <v-card-text class="px-6">
          Tem certeza que deseja remover <strong>{{ keyParaRemover }}</strong> do cofre?
          A próxima leitura usará variável de ambiente ou valor padrão.
        </v-card-text>
        <v-card-actions class="px-6 pb-5 ga-2">
          <v-spacer />
          <v-btn variant="text" @click="dialogRemover = false">Cancelar</v-btn>
          <v-btn color="error" variant="flat" :loading="deletingKey === keyParaRemover" @click="removerSegredo">Remover</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'
import { useStatusBanner } from '../composables/useStatusBanner'

const { loading, errorMessage, setLoading, setError } = useStatusBanner()
const secrets = ref([])
const total = ref(0)
const successMessage = ref('')

// vault init
const initLoading = ref(false)

// gravar
const dialogGravar = ref(false)
const saveLoading = ref(false)
const showValue = ref(false)
const form = ref({ key: '', value: '' })
const formErrors = ref({ key: '', value: '' })
const formError = ref('')

// remover
const dialogRemover = ref(false)
const deletingKey = ref('')
const keyParaRemover = ref('')

const countBySource = computed(() => {
  const counts = { env: 0, vault: 0, default: 0, absent: 0 }
  for (const secret of secrets.value) {
    const source = secret?.source || 'absent'
    if (source in counts) counts[source] += 1
  }
  return counts
})

const statusLabel = computed(() => {
  if (countBySource.value.vault > 0) return 'Cofre em uso'
  if (countBySource.value.env > 0) return 'Ambiente em uso'
  if (countBySource.value.default > 0) return 'Defaults ativos'
  return 'Sem diagnóstico'
})

const statusColor = computed(() => {
  if (countBySource.value.vault > 0) return 'success'
  if (countBySource.value.env > 0) return 'primary'
  if (countBySource.value.default > 0) return 'warning'
  return 'grey'
})

function sourceLabel(source) {
  return { env: 'Ambiente', vault: 'Cofre', default: 'Default', absent: 'Ausente' }[source] || source || 'Desconhecido'
}

function sourceColor(source) {
  return { env: 'primary', vault: 'success', default: 'warning', absent: 'grey' }[source] || 'grey'
}

async function loadSecrets() {
  setLoading()
  try {
    const response = await api.get('/v1/sistema/segredos-status')
    const data = response?.data?.data || {}
    secrets.value = data.segredos || []
    total.value = data.total || secrets.value.length
  } catch (error) {
    setError(error?.response?.data?.detail || error?.message || 'Erro ao carregar diagnóstico de segredos.')
  } finally {
    setLoading(false)
  }
}

async function inicializarVault() {
  initLoading.value = true
  try {
    const response = await api.post('/v1/cofre/init')
    const status = response?.data?.data?.status
    successMessage.value = status === 'ja_inicializado'
      ? 'Vault já estava inicializado.'
      : 'Vault inicializado com sucesso!'
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || 'Erro ao inicializar vault.'
  } finally {
    initLoading.value = false
  }
}

function abrirGravar(keyName = '') {
  form.value = { key: keyName, value: '' }
  formErrors.value = { key: '', value: '' }
  formError.value = ''
  showValue.value = false
  dialogGravar.value = true
}

function fecharGravar() {
  dialogGravar.value = false
}

async function gravarSegredo() {
  formErrors.value = { key: '', value: '' }
  formError.value = ''
  if (!form.value.key.trim()) { formErrors.value.key = 'Chave obrigatória'; return }
  if (!form.value.value.trim()) { formErrors.value.value = 'Valor obrigatório'; return }

  saveLoading.value = true
  try {
    await api.post('/v1/cofre/segredos', { key: form.value.key.trim(), value: form.value.value })
    successMessage.value = `Segredo "${form.value.key.trim()}" gravado no cofre.`
    fecharGravar()
    await loadSecrets()
  } catch (error) {
    formError.value = error?.response?.data?.detail || error?.message || 'Erro ao gravar segredo.'
  } finally {
    saveLoading.value = false
  }
}

function confirmarRemocao(key) {
  keyParaRemover.value = key
  dialogRemover.value = true
}

async function removerSegredo() {
  deletingKey.value = keyParaRemover.value
  try {
    await api.delete(`/v1/cofre/segredos/${keyParaRemover.value}`)
    successMessage.value = `Segredo "${keyParaRemover.value}" removido do cofre.`
    dialogRemover.value = false
    await loadSecrets()
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || 'Erro ao remover segredo.'
  } finally {
    deletingKey.value = ''
    keyParaRemover.value = ''
  }
}

onMounted(loadSecrets)
</script>

<style scoped>
.secrets-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.page-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.panel-card {
  border: 1px solid rgba(208, 208, 208, 0.9);
}

.summary-item {
  border: 1px solid rgba(208, 208, 208, 0.9);
  border-radius: 16px;
  padding: 14px;
  background: #f8fbff;
  height: 100%;
}

.summary-label {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface));
  opacity: 0.72;
  margin-bottom: 6px;
}

.summary-value {
  font-size: 24px;
  font-weight: 800;
  line-height: 1.1;
  color: rgb(var(--v-theme-primary));
}

.is-good {
  color: rgb(var(--v-theme-success));
}

.is-warning {
  color: rgb(var(--v-theme-warning));
}

.empty-cell {
  text-align: center;
  color: rgba(51, 51, 51, 0.7);
  padding: 24px 12px;
}

@media (max-width: 600px) {
  .summary-value {
    font-size: 20px;
  }
}
</style>
