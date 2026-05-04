<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h1>Requisitos</h1>
        <p class="muted requisitos-subtitle">
          Cadastre, acompanhe e priorize solicitações com contexto funcional e operacional.
        </p>
      </div>
      <div class="header-actions">
        <v-tooltip text="Recarrega a listagem atual de requisitos" location="top">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              variant="outlined"
              prepend-icon="mdi-refresh"
              :loading="store.carregando"
              @click="carregar"
            >
              Atualizar
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="Abre o formulário para registrar uma nova solicitação" location="top">
          <template #activator="{ props }">
            <v-btn v-bind="props" color="amber" prepend-icon="mdi-plus" @click="dialog = true">
              Novo requisito
            </v-btn>
          </template>
        </v-tooltip>
      </div>
    </div>

    <v-row class="mb-4">
      <v-col cols="12" md="4">
        <v-card class="table-card summary-card">
          <div class="muted">Total em lista</div>
          <div class="summary-value">{{ store.itens.length }}</div>
        </v-card>
      </v-col>
      <v-col cols="12" md="8">
        <v-alert type="info" variant="tonal">
          Use a lista para visão rápida e o formulário para registrar novas demandas com urgência, área e sistema de origem.
        </v-alert>
      </v-col>
    </v-row>

    <v-alert v-if="store.erro" type="error" variant="tonal" class="mb-4">
      {{ store.erro }}
    </v-alert>

    <v-skeleton-loader v-if="store.carregando" type="table" />
    <v-data-table v-else :headers="headers" :items="store.itens" item-value="id" class="table-card">
      <template v-slot:[`item.status`]="{ item }">
        <v-tooltip text="Situação atual do requisito no fluxo operacional" location="top">
          <template #activator="{ props }">
            <v-chip v-bind="props" size="small" :color="corStatus(item.status)">{{ item.status }}</v-chip>
          </template>
        </v-tooltip>
      </template>
    </v-data-table>

    <v-dialog v-model="dialog" width="760">
      <v-card>
        <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2">
          <span>Nova solicitação de requisito</span>
          <v-chip size="small" color="amber" variant="tonal">Cadastro guiado</v-chip>
        </v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="12" md="6">
              <v-tooltip text="Resumo curto e objetivo do requisito" location="top">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-text-field v-model="form.titulo" label="Título" variant="outlined" />
                  </div>
                </template>
              </v-tooltip>
            </v-col>
            <v-col cols="12" md="6">
              <v-tooltip text="Prioridade usada na triagem e ordenação do backlog" location="top">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-select v-model="form.urgencia" label="Urgência" variant="outlined" :items="['baixa', 'media', 'alta', 'critica']" />
                  </div>
                </template>
              </v-tooltip>
            </v-col>
          </v-row>

          <v-tooltip text="Explique a necessidade de negócio e o impacto esperado" location="top">
            <template #activator="{ props }">
              <div v-bind="props">
                <v-textarea v-model="form.descricao" label="Descrição" variant="outlined" rows="4" />
              </div>
            </template>
          </v-tooltip>

          <v-row>
            <v-col cols="12" md="4">
              <v-tooltip text="Área responsável ou demandante" location="top">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-text-field v-model="form.area" label="Área" variant="outlined" />
                  </div>
                </template>
              </v-tooltip>
            </v-col>
            <v-col cols="12" md="4">
              <v-tooltip text="Sistema impactado pela mudança" location="top">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-text-field v-model="form.sistema" label="Sistema" variant="outlined" />
                  </div>
                </template>
              </v-tooltip>
            </v-col>
            <v-col cols="12" md="4">
              <v-tooltip text="Usuário, área ou grupo que solicitou o requisito" location="top">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-text-field v-model="form.solicitante" label="Solicitante" variant="outlined" />
                  </div>
                </template>
              </v-tooltip>
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">Cancelar</v-btn>
          <v-btn color="amber" :loading="salvando" @click="salvar">Salvar</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </section>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRequisitosStore } from '../stores/requisitos'

const store = useRequisitosStore()
const dialog = ref(false)
const salvando = ref(false)

const form = reactive({
  titulo: 'Consulta prévia antes do cadastro rural',
  descricao: 'Ao informar CPF ou CNPJ, verificar se cliente já existe antes de criar novo cadastro.',
  urgencia: 'alta',
  area: 'Crédito',
  sistema: 'Portal Rural',
  solicitante: 'gerencia_credito',
})

const headers = [
  { title: 'Código', key: 'codigo' },
  { title: 'Título', key: 'titulo' },
  { title: 'Status', key: 'status' },
  { title: 'Urgência', key: 'urgencia' },
  { title: 'Área', key: 'area' },
]

onMounted(carregar)

function carregar() {
  store.listar()
}

function corStatus(status) {
  return ({ recebido: 'blue', em_analise: 'orange', aprovado: 'green', rejeitado: 'red' })[status] || 'grey'
}

async function salvar() {
  salvando.value = true
  try {
    await store.criar({ ...form })
    dialog.value = false
  } finally {
    salvando.value = false
  }
}
</script>

<style scoped>
.requisitos-subtitle {
  max-width: 58ch;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.summary-card {
  padding: 16px;
}

.summary-value {
  font-size: 30px;
  font-weight: 800;
  color: var(--accent);
}
</style>
