<template>
  <v-container fluid class="pa-4" data-testid="route-operational-deploy">
    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-4">
      <div>
        <h1 class="text-h5 font-weight-bold">Central de Administração Operacional</h1>
        <p class="text-body-2 text-medium-emphasis mb-0">
          Publicação governada do ReqSys em desenvolvimento, sem exposição de tokens ou acesso direto ao Fly.io.
        </p>
      </div>
      <v-chip color="success" variant="tonal">Produção não será tocada</v-chip>
    </div>

    <v-alert type="info" variant="tonal" class="mb-4">
      Em DEV, a política exige uma confirmação explícita. O ReqSys traduz a intenção para o workflow governado e registra a evidência da operação.
    </v-alert>

    <v-row>
      <v-col v-for="item in aplicacoes" :key="item.id" cols="12" md="6">
        <v-card variant="outlined" height="100%">
          <v-card-title>{{ item.titulo }}</v-card-title>
          <v-card-subtitle>{{ item.app_name }}</v-card-subtitle>
          <v-card-text>
            <div class="text-body-2 mb-3">Ambiente: <strong>Desenvolvimento</strong></div>
            <div class="text-body-2 mb-3">Origem: <strong>main</strong></div>
            <div class="text-body-2">Ação permitida nesta versão: <strong>Deploy</strong></div>
          </v-card-text>
          <v-card-actions>
            <v-btn
              color="primary"
              variant="flat"
              :loading="ocupado === item.id"
              :disabled="Boolean(ocupado)"
              @click="abrirConfirmacao(item)"
            >
              Publicar {{ item.id === 'backend' ? 'backend' : 'frontend' }} em DEV
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <v-alert v-if="erro" type="error" variant="tonal" class="mt-4">{{ erro }}</v-alert>

    <v-card v-if="resultado" variant="outlined" class="mt-4">
      <v-card-title>Operação solicitada</v-card-title>
      <v-card-text>
        <v-list density="compact">
          <v-list-item title="Status" :subtitle="resultado.status" />
          <v-list-item title="Aplicação" :subtitle="resultado.app_name" />
          <v-list-item title="Ambiente" :subtitle="resultado.ambiente" />
          <v-list-item title="Correlation ID" :subtitle="resultado.correlation_id" />
          <v-list-item title="Produção afetada" :subtitle="resultado.production_touched ? 'Sim' : 'Não'" />
        </v-list>
      </v-card-text>
    </v-card>

    <v-dialog v-model="dialogo" max-width="560">
      <v-card>
        <v-card-title>Confirmar deploy em DEV</v-card-title>
        <v-card-text v-if="selecionada">
          <p class="mb-3">
            Você está solicitando a publicação de <strong>{{ selecionada.titulo }}</strong> em desenvolvimento.
          </p>
          <v-alert type="success" variant="tonal" density="compact">
            Esta operação não altera homologação nem produção.
          </v-alert>
          <div v-if="validacao" class="mt-3 text-body-2">
            Operação validada: <strong>{{ validacao.operacao_id }}</strong><br>
            Correlation ID: <strong>{{ validacao.correlation_id }}</strong>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dialogo = false">Cancelar</v-btn>
          <v-btn color="primary" variant="flat" :loading="Boolean(ocupado)" @click="confirmarDeploy">
            Confirmar e executar
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import {
  carregarCatalogoDeploy,
  executarDeploy,
  mensagemErroDeploy,
  validarDeploy,
} from '../services/operationalDeploy'

const aplicacoes = ref([])
const selecionada = ref(null)
const validacao = ref(null)
const resultado = ref(null)
const erro = ref('')
const dialogo = ref(false)
const ocupado = ref('')

async function carregar() {
  erro.value = ''
  try {
    const catalogo = await carregarCatalogoDeploy()
    aplicacoes.value = catalogo.aplicacoes || []
  } catch (e) {
    erro.value = mensagemErroDeploy(e)
  }
}

async function abrirConfirmacao(item) {
  selecionada.value = item
  validacao.value = null
  erro.value = ''
  ocupado.value = item.id
  try {
    validacao.value = await validarDeploy(item.id)
    dialogo.value = true
  } catch (e) {
    erro.value = mensagemErroDeploy(e)
  } finally {
    ocupado.value = ''
  }
}

async function confirmarDeploy() {
  if (!selecionada.value) return
  erro.value = ''
  ocupado.value = selecionada.value.id
  try {
    resultado.value = await executarDeploy(selecionada.value.id)
    dialogo.value = false
  } catch (e) {
    erro.value = mensagemErroDeploy(e)
  } finally {
    ocupado.value = ''
  }
}

onMounted(carregar)
</script>
