<template>
  <div>
    <!-- Cabeçalho -->
    <div class="d-flex flex-wrap align-center gap-3 mb-6">
      <v-btn variant="text" prepend-icon="mdi-arrow-left" :to="'/requisitos'" size="small">
        Voltar
      </v-btn>
      <v-divider vertical class="mx-1" style="height:24px" />
      <div class="flex-grow-1">
        <div class="text-h5 font-weight-bold mb-1">{{ requisito?.titulo || 'Carregando...' }}</div>
        <div class="text-body-2 text-medium-emphasis">Detalhes do requisito #{{ id }}</div>
      </div>
      <v-btn color="primary" prepend-icon="mdi-pencil-outline" @click="dialogAberto = true" :disabled="!requisito">
        Editar
      </v-btn>
    </div>

    <v-row v-if="carregando">
      <v-col cols="12" class="d-flex justify-center pa-12">
        <v-progress-circular indeterminate color="primary" />
      </v-col>
    </v-row>

    <v-row v-else-if="requisito">
      <!-- Coluna principal -->
      <v-col cols="12" md="8">
        <!-- Descrição -->
        <v-card rounded="xl" :elevation="2" class="mb-4">
          <v-card-title class="pa-5 pb-2">
            <v-icon color="primary" class="mr-2">mdi-text-long</v-icon>
            Descrição
          </v-card-title>
          <v-card-text class="pa-5 pt-2">
            <p v-if="requisito.descricao" class="text-body-1">{{ requisito.descricao }}</p>
            <p v-else class="text-body-2 text-medium-emphasis font-italic">Nenhuma descrição cadastrada.</p>
          </v-card-text>
        </v-card>

        <!-- Histórico / Linha do tempo -->
        <v-card rounded="xl" :elevation="2" class="mb-4">
          <v-card-title class="pa-5 pb-2">
            <v-icon color="primary" class="mr-2">mdi-timeline-clock-outline</v-icon>
            Histórico de Status
          </v-card-title>
          <v-card-text class="pa-5 pt-2">
            <v-timeline side="end" density="compact" truncate-line="both">
              <v-timeline-item
                v-for="(evt, i) in historico"
                :key="i"
                :dot-color="evt.cor"
                size="small"
              >
                <div class="d-flex align-center gap-2">
                  <v-chip :color="evt.cor" size="x-small" variant="tonal">{{ evt.status }}</v-chip>
                  <span class="text-caption text-medium-emphasis">{{ evt.data }}</span>
                </div>
                <div v-if="evt.obs" class="text-caption mt-1">{{ evt.obs }}</div>
              </v-timeline-item>
            </v-timeline>
            <p v-if="!historico.length" class="text-body-2 text-medium-emphasis font-italic">Sem histórico registrado.</p>
          </v-card-text>
        </v-card>

        <!-- Rastreabilidade -->
        <v-card rounded="xl" :elevation="2">
          <v-card-title class="pa-5 pb-2">
            <v-icon color="primary" class="mr-2">mdi-link-variant</v-icon>
            Rastreabilidade
          </v-card-title>
          <v-card-text class="pa-5 pt-2">
            <div v-if="rastreabilidade.length">
              <v-chip
                v-for="item in rastreabilidade"
                :key="item"
                class="ma-1"
                variant="tonal"
                color="secondary"
                size="small"
              >
                {{ item }}
              </v-chip>
            </div>
            <p v-else class="text-body-2 text-medium-emphasis font-italic">Nenhum vínculo de rastreabilidade.</p>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Coluna lateral -->
      <v-col cols="12" md="4">
        <!-- Metadados -->
        <v-card rounded="xl" :elevation="2" class="mb-4">
          <v-card-title class="pa-5 pb-2">
            <v-icon color="primary" class="mr-2">mdi-information-outline</v-icon>
            Informações
          </v-card-title>
          <v-card-text class="pa-5 pt-2">
            <v-list density="compact" class="pa-0">
              <v-list-item class="px-0 py-2">
                <template #prepend>
                  <v-icon size="18" color="medium-emphasis" class="mr-3">mdi-identifier</v-icon>
                </template>
                <v-list-item-title class="text-caption text-medium-emphasis">ID</v-list-item-title>
                <v-list-item-subtitle class="font-weight-medium">{{ requisito.id }}</v-list-item-subtitle>
              </v-list-item>
              <v-divider />
              <v-list-item class="px-0 py-2">
                <template #prepend>
                  <v-icon size="18" color="medium-emphasis" class="mr-3">mdi-tag-outline</v-icon>
                </template>
                <v-list-item-title class="text-caption text-medium-emphasis">Status</v-list-item-title>
                <v-list-item-subtitle>
                  <v-chip :color="corStatus(requisito.status)" size="x-small" variant="tonal">
                    {{ requisito.status }}
                  </v-chip>
                </v-list-item-subtitle>
              </v-list-item>
              <v-divider />
              <v-list-item class="px-0 py-2">
                <template #prepend>
                  <v-icon size="18" color="medium-emphasis" class="mr-3">mdi-alert-circle-outline</v-icon>
                </template>
                <v-list-item-title class="text-caption text-medium-emphasis">Urgência</v-list-item-title>
                <v-list-item-subtitle>
                  <v-chip :color="corUrgencia(requisito.urgencia)" size="x-small" variant="tonal">
                    {{ requisito.urgencia }}
                  </v-chip>
                </v-list-item-subtitle>
              </v-list-item>
              <v-divider />
              <v-list-item class="px-0 py-2">
                <template #prepend>
                  <v-icon size="18" color="medium-emphasis" class="mr-3">mdi-domain</v-icon>
                </template>
                <v-list-item-title class="text-caption text-medium-emphasis">Área</v-list-item-title>
                <v-list-item-subtitle class="font-weight-medium">{{ requisito.area || '—' }}</v-list-item-subtitle>
              </v-list-item>
              <v-divider />
              <v-list-item class="px-0 py-2">
                <template #prepend>
                  <v-icon size="18" color="medium-emphasis" class="mr-3">mdi-monitor</v-icon>
                </template>
                <v-list-item-title class="text-caption text-medium-emphasis">Sistema</v-list-item-title>
                <v-list-item-subtitle class="font-weight-medium">{{ requisito.sistema || '—' }}</v-list-item-subtitle>
              </v-list-item>
              <v-divider />
              <v-list-item class="px-0 py-2">
                <template #prepend>
                  <v-icon size="18" color="medium-emphasis" class="mr-3">mdi-account-outline</v-icon>
                </template>
                <v-list-item-title class="text-caption text-medium-emphasis">Solicitante</v-list-item-title>
                <v-list-item-subtitle class="font-weight-medium">{{ requisito.solicitante || '—' }}</v-list-item-subtitle>
              </v-list-item>
              <template v-if="requisito.criado_em || requisito.atualizado_em">
                <v-divider />
                <v-list-item v-if="requisito.criado_em" class="px-0 py-2">
                  <template #prepend>
                    <v-icon size="18" color="medium-emphasis" class="mr-3">mdi-calendar-plus-outline</v-icon>
                  </template>
                  <v-list-item-title class="text-caption text-medium-emphasis">Criado em</v-list-item-title>
                  <v-list-item-subtitle class="font-weight-medium">{{ formatarData(requisito.criado_em) }}</v-list-item-subtitle>
                </v-list-item>
                <v-divider v-if="requisito.atualizado_em" />
                <v-list-item v-if="requisito.atualizado_em" class="px-0 py-2">
                  <template #prepend>
                    <v-icon size="18" color="medium-emphasis" class="mr-3">mdi-calendar-edit-outline</v-icon>
                  </template>
                  <v-list-item-title class="text-caption text-medium-emphasis">Atualizado em</v-list-item-title>
                  <v-list-item-subtitle class="font-weight-medium">{{ formatarData(requisito.atualizado_em) }}</v-list-item-subtitle>
                </v-list-item>
              </template>
            </v-list>
          </v-card-text>
        </v-card>

        <!-- Ações rápidas -->
        <v-card rounded="xl" :elevation="1">
          <v-card-title class="pa-5 pb-2">
            <v-icon color="primary" class="mr-2">mdi-flash-outline</v-icon>
            Ações Rápidas
          </v-card-title>
          <v-card-text class="pa-4 pt-2 d-flex flex-column gap-2">
            <v-btn
              v-for="acao in acoesRapidas"
              :key="acao.label"
              :color="acao.cor"
              variant="tonal"
              block
              :prepend-icon="acao.icon"
              size="small"
              @click="mudarStatus(acao.status)"
              :disabled="requisito.status === acao.status || salvando"
            >
              {{ acao.label }}
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-alert v-else type="error" variant="tonal" class="ma-4">
      Requisito não encontrado.
    </v-alert>

    <!-- Dialog de edição -->
    <v-dialog v-model="dialogAberto" max-width="760" scrollable>
      <v-card rounded="xl">
        <v-card-title class="pa-6 pb-2">Editar Requisito</v-card-title>
        <v-divider />
        <v-card-text class="pa-6">
          <v-row dense>
            <v-col cols="12">
              <v-text-field v-model="form.titulo" label="Título *" variant="outlined" density="comfortable" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-select v-model="form.urgencia" :items="urgenciaOpcoes" label="Urgência *" variant="outlined" density="comfortable" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-select v-model="form.status" :items="statusOpcoes" label="Status" variant="outlined" density="comfortable" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model="form.area" label="Área" variant="outlined" density="comfortable" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model="form.sistema" label="Sistema" variant="outlined" density="comfortable" />
            </v-col>
            <v-col cols="12">
              <v-text-field v-model="form.solicitante" label="Solicitante" variant="outlined" density="comfortable" />
            </v-col>
            <v-col cols="12">
              <v-textarea v-model="form.descricao" label="Descrição" variant="outlined" rows="4" auto-grow />
            </v-col>
          </v-row>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="dialogAberto = false">Cancelar</v-btn>
          <v-btn color="primary" :loading="salvando" @click="salvar">Salvar</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../services/api'

const route = useRoute()
const id = route.params.id

const carregando = ref(true)
const salvando = ref(false)
const dialogAberto = ref(false)
const requisito = ref(null)
const form = ref({})

const statusOpcoes = ['ABERTO', 'EM_ANÁLISE', 'APROVADO', 'REJEITADO', 'IMPLEMENTADO']
const urgenciaOpcoes = ['BAIXA', 'MÉDIA', 'ALTA', 'CRÍTICA']

const historico = ref([])
const rastreabilidade = ref([])

const acoesRapidas = [
  { label: 'Marcar Em Análise', status: 'EM_ANÁLISE', cor: 'warning', icon: 'mdi-eye-check-outline' },
  { label: 'Aprovar', status: 'APROVADO', cor: 'success', icon: 'mdi-check-circle-outline' },
  { label: 'Rejeitar', status: 'REJEITADO', cor: 'error', icon: 'mdi-close-circle-outline' },
  { label: 'Marcar Implementado', status: 'IMPLEMENTADO', cor: 'secondary', icon: 'mdi-rocket-launch-outline' },
]

function corStatus(s) {
  return { ABERTO: 'info', EM_ANÁLISE: 'warning', APROVADO: 'success', REJEITADO: 'error', IMPLEMENTADO: 'secondary' }[s] || 'default'
}
function corUrgencia(u) {
  return { BAIXA: 'success', MÉDIA: 'info', ALTA: 'warning', CRÍTICA: 'error' }[u] || 'default'
}
function formatarData(val) {
  if (!val) return '—'
  return new Date(val).toLocaleString('pt-BR')
}

function abrirEdicao() {
  form.value = { ...requisito.value }
  dialogAberto.value = true
}

async function salvar() {
  salvando.value = true
  try {
    const { data } = await api.put(`/v1/requisitos/${id}`, form.value)
    requisito.value = data
    dialogAberto.value = false
  } catch (e) {
    console.error(e)
  } finally {
    salvando.value = false
  }
}

async function mudarStatus(novoStatus) {
  salvando.value = true
  try {
    const payload = { ...requisito.value, status: novoStatus }
    const { data } = await api.put(`/v1/requisitos/${id}`, payload)
    requisito.value = data
    historico.value.unshift({ status: novoStatus, cor: corStatus(novoStatus), data: formatarData(new Date()), obs: 'Status atualizado manualmente.' })
  } catch (e) {
    console.error(e)
  } finally {
    salvando.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await api.get(`/v1/requisitos/${id}`)
    requisito.value = data
    form.value = { ...data }

    if (data.historico) historico.value = data.historico
    if (data.rastreabilidade) rastreabilidade.value = data.rastreabilidade
  } catch {
    // fallback para mock quando API não disponível
    const mocks = [
      { id: 1, titulo: 'Autenticação SSO', sistema: 'Portal', area: 'TI', solicitante: 'João Silva', urgencia: 'ALTA', status: 'APROVADO', descricao: 'Implementar autenticação Single Sign-On via Active Directory para todos os usuários do Portal corporativo.', criado_em: '2026-01-10T09:00:00', atualizado_em: '2026-03-15T14:30:00' },
      { id: 2, titulo: 'Exportar relatório PDF', sistema: 'SSRS', area: 'Financeiro', solicitante: 'Maria Costa', urgencia: 'MÉDIA', status: 'ABERTO', descricao: 'Adicionar opção de exportação de relatórios financeiros para formato PDF com logo institucional.' },
      { id: 3, titulo: 'Dashboard executivo', sistema: 'BI', area: 'Diretoria', solicitante: 'Pedro Alves', urgencia: 'CRÍTICA', status: 'EM_ANÁLISE', descricao: 'Criar painel executivo com KPIs estratégicos, atualizados em tempo real, com drill-down por área.' },
    ]
    requisito.value = mocks.find(m => String(m.id) === String(id)) || null
    if (requisito.value) {
      form.value = { ...requisito.value }
      historico.value = [
        { status: requisito.value.status, cor: corStatus(requisito.value.status), data: formatarData(requisito.value.atualizado_em || new Date()), obs: 'Status atual.' },
        { status: 'ABERTO', cor: 'info', data: formatarData(requisito.value.criado_em || new Date()), obs: 'Requisito criado.' },
      ]
    }
  } finally {
    carregando.value = false
  }
})
</script>
