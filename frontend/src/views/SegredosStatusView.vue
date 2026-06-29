<template>
  <section class="page" data-testid="route-segredos-status">
    <PageHeader
      title="Status de Segredos"
      subtitle="Diagnóstico da origem dos segredos do backend, sem exposição de valores."
      :chip="statusChipText"
      :chip-color="statusChipColor"
      chip-tooltip="Indica a origem predominante dos segredos configurados"
    >
      <template #actions>
        <v-tooltip text="Grava um segredo criptografado no cofre local" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              color="success"
              variant="outlined"
              prepend-icon="mdi-lock-plus-outline"
              data-testid="btn-gravar-segredo"
              @click="abrirGravar()"
            >
              Gravar segredo
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Cria a master key do cofre (uma vez por ambiente)" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              color="secondary"
              variant="outlined"
              prepend-icon="mdi-cog-play-outline"
              :loading="initLoading"
              data-testid="btn-inicializar-vault"
              @click="inicializarVault"
            >
              Inicializar cofre
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Recarrega o diagnóstico de segredos do backend" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              size="small"
              variant="outlined"
              prepend-icon="mdi-refresh"
              :loading="carregando"
              data-testid="btn-atualizar"
              @click="carregar"
            >
              Atualizar
            </v-btn>
          </template>
        </v-tooltip>
      </template>
    </PageHeader>

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4" data-testid="alerta-erro">
      {{ erro }}
    </v-alert>
    <v-alert
      v-if="sucesso"
      type="success"
      variant="tonal"
      class="mb-4"
      closable
      data-testid="alerta-sucesso"
      @click:close="sucesso = ''"
    >
      {{ sucesso }}
    </v-alert>

    <v-row>
      <v-col cols="12" md="4">
        <v-card class="table-card h-100">
          <v-card-title class="py-3 px-4">Resumo</v-card-title>
          <v-divider />
          <v-card-text>
            <v-skeleton-loader v-if="carregando" type="list-item-three-line" />
            <div v-else class="summary-grid">
              <div class="summary-item">
                <div class="muted">Total monitorado</div>
                <strong class="summary-value" data-testid="total">{{ total }}</strong>
              </div>
              <div class="summary-item">
                <div class="muted">Via ambiente</div>
                <strong class="summary-value">{{ countBySource.env }}</strong>
              </div>
              <div class="summary-item">
                <div class="muted">Via cofre</div>
                <strong class="summary-value">{{ countBySource.vault }}</strong>
              </div>
              <div class="summary-item">
                <div class="muted">Usando default</div>
                <strong class="summary-value" :class="{ 'text-amber': countBySource.default > 0 }">
                  {{ countBySource.default }}
                </strong>
              </div>
            </div>

            <v-alert type="info" variant="tonal" class="mt-4" density="compact">
              Os valores dos segredos <strong>nunca</strong> são retornados pela API —
              apenas a origem da configuração.
            </v-alert>

            <v-alert
              v-if="!carregando && countBySource.default > 0"
              type="warning"
              variant="tonal"
              class="mt-3"
              density="compact"
              data-testid="alerta-default"
            >
              {{ countBySource.default }} segredo(s) usando valor padrão. Considere configurar via ambiente ou cofre.
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="8">
        <v-card class="table-card">
          <v-card-title class="py-3 px-4">Segredos monitorados</v-card-title>
          <v-divider />

          <v-skeleton-loader v-if="carregando" type="table-row-divider@5" />
          <v-table v-else data-testid="tabela-segredos">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Origem</th>
                <th>Resolvido</th>
                <th>Cofre / Serviço</th>
                <th class="actions-col"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="segredo in segredos" :key="segredo.name" :data-testid="`row-${segredo.name}`">
                <td>
                  <div class="secret-name">{{ segredo.name }}</div>
                  <div class="muted text-caption">env: {{ segredo.env_name || segredo.name }}</div>
                </td>
                <td>
                  <StatusChip
                    :value="segredo.source"
                    :tooltip="sourceTooltip(segredo.source)"
                    data-testid="chip-origem"
                  />
                </td>
                <td>
                  <v-tooltip :text="segredo.resolved ? 'Valor disponível' : 'Não configurado'" location="top">
                    <template #activator="{ props }">
                      <v-icon
                        v-bind="props"
                        :icon="segredo.resolved ? 'mdi-check-circle' : 'mdi-alert-circle'"
                        :color="segredo.resolved ? 'green' : 'grey'"
                        size="20"
                        :data-testid="`resolved-${segredo.name}`"
                      />
                    </template>
                  </v-tooltip>
                </td>
                <td>
                  <span v-if="segredo.vault_key" class="text-caption">
                    <strong>{{ segredo.vault_key }}</strong>
                    <span v-if="segredo.vault_service_name" class="muted"> · {{ segredo.vault_service_name }}</span>
                  </span>
                  <span v-else class="muted">—</span>
                </td>
                <td class="actions-col">
                  <div class="row-actions">
                    <v-tooltip text="Gravar no cofre" location="top">
                      <template #activator="{ props }">
                        <v-btn
                          v-bind="props"
                          icon="mdi-pencil-outline"
                          size="x-small"
                          variant="text"
                          color="primary"
                          :data-testid="`btn-gravar-${segredo.name}`"
                          @click="abrirGravar(segredo.name)"
                        />
                      </template>
                    </v-tooltip>
                    <v-tooltip v-if="segredo.source === 'vault'" text="Remover do cofre" location="top">
                      <template #activator="{ props }">
                        <v-btn
                          v-bind="props"
                          icon="mdi-delete-outline"
                          size="x-small"
                          variant="text"
                          color="error"
                          :loading="removendoKey === segredo.name"
                          :data-testid="`btn-remover-${segredo.name}`"
                          @click="confirmarRemocao(segredo.name)"
                        />
                      </template>
                    </v-tooltip>
                  </div>
                </td>
              </tr>
              <tr v-if="!segredos.length">
                <td colspan="5" class="empty-cell">Nenhum diagnóstico retornado.</td>
              </tr>
            </tbody>
          </v-table>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="table-card mt-4" data-testid="secao-testes-cofre">
      <v-card-title class="py-3 px-4 d-flex align-center flex-wrap ga-2">
        <span>Testes aplicados</span>
        <v-chip size="small" color="success" variant="tonal" data-testid="chip-total-testes">
          {{ totalTestes }} testes
        </v-chip>
        <v-chip size="small" color="primary" variant="tonal">
          {{ testesApi }} API
        </v-chip>
        <v-chip size="small" color="secondary" variant="tonal">
          {{ testesServico }} serviço
        </v-chip>
        <v-chip size="small" color="amber" variant="tonal">
          {{ testesE2e }} E2E
        </v-chip>
      </v-card-title>
      <v-divider />
      <v-card-text class="px-4 pb-4">
        <v-alert type="info" variant="tonal" density="compact" class="mb-4">
          Matriz de evidência Padrão Ouro do cofre. Comando CI:
          <code class="test-cmd">{{ catalogoTestes.comando }}</code>
        </v-alert>

        <v-expansion-panels variant="accordion" multiple>
          <v-expansion-panel
            v-for="suite in catalogoTestes.suites"
            :key="suite.id"
            :data-testid="`suite-${suite.id}`"
          >
            <v-expansion-panel-title>
              <div class="suite-title">
                <span class="suite-alvo">{{ suite.alvo }}</span>
                <span class="muted text-caption">{{ suite.grupo }} · {{ suite.testes.length }} teste(s)</span>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div class="suite-meta muted text-caption mb-3">
                {{ suite.arquivo }} — {{ suite.classe }}
              </div>
              <ul class="test-list">
                <li
                  v-for="teste in suite.testes"
                  :key="`${suite.id}-${teste}`"
                  class="test-item"
                  :data-testid="`teste-${suite.id}-${teste}`"
                >
                  <v-icon icon="mdi-check-circle" color="success" size="16" class="mr-2" />
                  <span>{{ formatTestName(teste) }}</span>
                </li>
              </ul>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>
    </v-card>

    <v-dialog v-model="dialogGravar" max-width="500" persistent>
      <v-card>
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
            :type="mostrarValor ? 'text' : 'password'"
            :append-inner-icon="mostrarValor ? 'mdi-eye-off' : 'mdi-eye'"
            :error-messages="formErrors.value"
            @click:append-inner="mostrarValor = !mostrarValor"
          />
          <v-alert v-if="formErro" type="error" variant="tonal" density="compact" class="mt-2">
            {{ formErro }}
          </v-alert>
        </v-card-text>
        <v-card-actions class="px-6 pb-5">
          <v-spacer />
          <v-btn variant="text" @click="fecharGravar">Cancelar</v-btn>
          <v-btn color="success" variant="flat" :loading="gravando" data-testid="btn-confirmar-gravar" @click="gravarSegredo">
            Gravar
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="dialogRemover" max-width="420">
      <v-card>
        <v-card-title class="pt-5 px-6">Remover segredo</v-card-title>
        <v-card-text class="px-6">
          Tem certeza que deseja remover <strong>{{ keyParaRemover }}</strong> do cofre?
          A próxima leitura usará variável de ambiente ou valor padrão.
        </v-card-text>
        <v-card-actions class="px-6 pb-5">
          <v-spacer />
          <v-btn variant="text" @click="dialogRemover = false">Cancelar</v-btn>
          <v-btn color="error" variant="flat" :loading="!!removendoKey" data-testid="btn-confirmar-remover" @click="removerSegredo">
            Remover
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../services/api'
import PageHeader from '../components/PageHeader.vue'
import StatusChip from '../components/StatusChip.vue'
import { useAsyncLoader } from '../composables/useAsyncLoader.js'
import { COFRE_TEST_CATALOG, countCofreTestsByGrupo, formatTestName, totalCofreTests } from '../constants/cofreTestCatalog.js'

const catalogoTestes = COFRE_TEST_CATALOG
const totalTestes = totalCofreTests()
const testesApi = countCofreTestsByGrupo('API')
const testesServico = countCofreTestsByGrupo('Serviço')
const testesE2e = countCofreTestsByGrupo('E2E')

const { carregando, erro, run } = useAsyncLoader()

const segredos = ref([])
const total = ref(0)
const sucesso = ref('')
const initLoading = ref(false)
const gravando = ref(false)
const removendoKey = ref('')
const dialogGravar = ref(false)
const dialogRemover = ref(false)
const keyParaRemover = ref('')
const mostrarValor = ref(false)
const form = ref({ key: '', value: '' })
const formErrors = ref({ key: '', value: '' })
const formErro = ref('')

const countBySource = computed(() => {
  const counts = { env: 0, vault: 0, default: 0, absent: 0 }
  for (const s of segredos.value) {
    const source = s?.source || 'absent'
    if (source in counts) counts[source] += 1
  }
  return counts
})

const statusChipText = computed(() => {
  if (erro.value) return 'Falha de leitura'
  if (countBySource.value.vault > 0) return 'Cofre em uso'
  if (countBySource.value.env > 0) return 'Ambiente em uso'
  return 'Aguardando diagnóstico'
})

const statusChipColor = computed(() => {
  if (erro.value) return 'red'
  if (countBySource.value.vault > 0) return 'green'
  if (countBySource.value.env > 0) return 'amber'
  return 'grey'
})

function sourceTooltip(source) {
  return {
    env:     'Lido de variável de ambiente',
    vault:   'Lido do cofre de segredos encriptado',
    default: 'Usando valor padrão — configure via ambiente ou cofre',
    absent:  'Não configurado em nenhuma origem',
  }[source] || source
}

async function carregar() {
  await run(async () => {
    const { data } = await api.get('/v1/sistema/segredos-status')
    const payload = data?.data || {}
    segredos.value = payload.segredos || []
    total.value = payload.total || segredos.value.length
  })
}

async function inicializarVault() {
  initLoading.value = true
  sucesso.value = ''
  try {
    const { data } = await api.post('/v1/cofre/init')
    const status = data?.data?.status
    sucesso.value = status === 'ja_inicializado'
      ? 'Cofre já estava inicializado.'
      : 'Cofre inicializado com sucesso.'
  } catch (error) {
    erro.value = error?.response?.data?.detail || error?.message || 'Erro ao inicializar cofre.'
  } finally {
    initLoading.value = false
  }
}

function abrirGravar(keyName = '') {
  form.value = { key: keyName, value: '' }
  formErrors.value = { key: '', value: '' }
  formErro.value = ''
  mostrarValor.value = false
  dialogGravar.value = true
}

function fecharGravar() {
  dialogGravar.value = false
}

async function gravarSegredo() {
  formErrors.value = { key: '', value: '' }
  formErro.value = ''
  if (!form.value.key.trim()) {
    formErrors.value.key = 'Chave obrigatória'
    return
  }
  if (!form.value.value.trim()) {
    formErrors.value.value = 'Valor obrigatório'
    return
  }

  gravando.value = true
  try {
    await api.post('/v1/cofre/segredos', {
      key: form.value.key.trim(),
      value: form.value.value,
    })
    sucesso.value = `Segredo "${form.value.key.trim()}" gravado no cofre.`
    fecharGravar()
    await carregar()
  } catch (error) {
    formErro.value = error?.response?.data?.detail || error?.message || 'Erro ao gravar segredo.'
  } finally {
    gravando.value = false
  }
}

function confirmarRemocao(key) {
  keyParaRemover.value = key
  dialogRemover.value = true
}

async function removerSegredo() {
  removendoKey.value = keyParaRemover.value
  try {
    await api.delete(`/v1/cofre/segredos/${keyParaRemover.value}`)
    sucesso.value = `Segredo "${keyParaRemover.value}" removido do cofre.`
    dialogRemover.value = false
    await carregar()
  } catch (error) {
    erro.value = error?.response?.data?.detail || error?.message || 'Erro ao remover segredo.'
  } finally {
    removendoKey.value = ''
    keyParaRemover.value = ''
  }
}

onMounted(carregar)
</script>

<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.summary-item {
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
}

.summary-value {
  font-size: 1.4rem;
  font-weight: 700;
}

.text-amber {
  color: rgb(var(--v-theme-amber));
}

.secret-name {
  font-weight: 600;
}

.empty-cell {
  text-align: center;
  color: var(--muted);
  padding: 24px 12px;
}

.actions-col {
  width: 88px;
  text-align: right;
}

.row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 2px;
}

.suite-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.suite-alvo {
  font-weight: 600;
}

.test-cmd {
  font-family: ui-monospace, monospace;
  font-size: 0.85em;
}

.test-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 6px;
}

.test-item {
  display: flex;
  align-items: flex-start;
  font-size: 0.9rem;
}
</style>
