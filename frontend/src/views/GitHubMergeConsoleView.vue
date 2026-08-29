<template>
  <main class="merge-console" data-testid="route-github-merge" aria-labelledby="merge-title">
    <PageHeader
      title="Console de Integração de alterações Governado"
      subtitle="Valide o SHA e solicite merges assíncronos de PRs empilhadas sem expor credenciais no navegador."
    />

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4" role="alert">{{ erro }}</v-alert>
    <v-alert v-if="mensagem" type="success" variant="tonal" class="mb-4" role="status">{{ mensagem }}</v-alert>

    <v-card class="pa-5 mb-5" variant="outlined">
      <v-card-title>1. Carregar pull request</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" md="8">
            <v-text-field v-model.trim="repositorio" label="Repositório" placeholder="owner/repo" />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field v-model.number="pullRequest" label="Número da Solicitação de integração" type="number" min="1" />
          </v-col>
        </v-row>
        <v-btn color="primary" :loading="carregando" :disabled="!podeConsultar" @click="consultar">
          Validar Solicitação de integração
        </v-btn>
      </v-card-text>
    </v-card>

    <template v-if="pr">
      <v-row class="mb-2">
        <v-col cols="12" sm="6" lg="3"><v-card class="pa-4" variant="tonal"><small>Estado</small><h3>{{ pr.estado }}</h3></v-card></v-col>
        <v-col cols="12" sm="6" lg="3"><v-card class="pa-4" variant="tonal"><small>Pode ser integrado</small><h3>{{ pr.mergeavel === true ? 'Sim' : pr.mergeavel === false ? 'Não' : 'Calculando' }}</h3></v-card></v-col>
        <v-col cols="12" sm="6" lg="3"><v-card class="pa-4" variant="tonal"><small>Checks aprovados</small><h3>{{ pr.checks.aprovados }}/{{ pr.checks.total }}</h3></v-card></v-col>
        <v-col cols="12" sm="6" lg="3"><v-card class="pa-4" variant="tonal"><small>Bloqueadores</small><h3>{{ pr.checks.bloqueadores.length }}</h3></v-card></v-col>
      </v-row>

      <v-card class="pa-5" variant="outlined">
        <v-card-title>2. Confirmar integração de alterações assíncrono</v-card-title>
        <v-card-text>
          <p class="mb-3"><strong>{{ pr.titulo }}</strong></p>
          <dl class="merge-details mb-5">
            <div><dt>Fluxo</dt><dd>{{ pr.branch_origem }} → {{ pr.branch_destino }}</dd></div>
            <div><dt>SHA protegido</dt><dd><code>{{ pr.sha }}</code></dd></div>
          </dl>
          <v-row>
            <v-col cols="12" md="6">
              <v-select v-model="metodo" label="Método" :items="['squash', 'merge', 'rebase']" />
            </v-col>
            <v-col cols="12" md="6">
              <v-select v-model="acao" label="Ação" :items="['default', 'merge_queue', 'direct_merge']" />
            </v-col>
          </v-row>
          <v-text-field v-model.trim="tituloCommit" label="Título do commit" maxlength="256" />
          <v-textarea v-model.trim="mensagemCommit" label="Mensagem do commit" maxlength="4096" rows="3" />
          <v-checkbox
            v-model="confirmado"
            label="Confirmo o repositório, a Solicitação de integração, o destino e o SHA exibidos acima."
          />
          <v-btn
            color="success"
            :loading="executando"
            :disabled="!podeExecutar"
            @click="executar"
          >
            Solicitar integração de alterações assíncrono
          </v-btn>
        </v-card-text>
      </v-card>

      <v-card v-if="resultado" class="pa-5 mt-5" variant="outlined">
        <v-card-title>Resultado</v-card-title>
        <pre class="resultado-json">{{ JSON.stringify(resultado, null, 2) }}</pre>
      </v-card>
    </template>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'
import PageHeader from '../components/PageHeader.vue'
import { api } from '../services/api'

const repositorio = ref('ericson-j-santos/reqsys-v2-enterprise-real')
const pullRequest = ref(null)
const pr = ref(null)
const metodo = ref('squash')
const acao = ref('default')
const tituloCommit = ref('')
const mensagemCommit = ref('')
const confirmado = ref(false)
const carregando = ref(false)
const executando = ref(false)
const erro = ref('')
const mensagem = ref('')
const resultado = ref(null)

const podeConsultar = computed(() => /^[\w.-]+\/[\w.-]+$/.test(repositorio.value) && Number(pullRequest.value) > 0)
const podeExecutar = computed(() => confirmado.value && tituloCommit.value && !pr.value?.checks?.bloqueadores?.length)

function detalheErro(error) {
  const detail = error?.response?.data?.detail
  return typeof detail === 'string' ? detail : detail?.mensagem || error.message || 'Falha inesperada.'
}

async function consultar() {
  carregando.value = true
  erro.value = ''
  mensagem.value = ''
  resultado.value = null
  confirmado.value = false
  try {
    const response = await api.get(`/v1/admin/github-merge/pull-requests/${pullRequest.value}`, {
      params: { repositorio: repositorio.value },
    })
    pr.value = response.data.data
    tituloCommit.value = `${pr.value.titulo} (#${pullRequest.value})`
    mensagemCommit.value = `Integração de alterações assíncrono governado pelo ReqSys para o SHA ${pr.value.sha}.`
  } catch (error) {
    pr.value = null
    erro.value = detalheErro(error)
  } finally {
    carregando.value = false
  }
}

async function executar() {
  executando.value = true
  erro.value = ''
  mensagem.value = ''
  try {
    const response = await api.post('/v1/admin/github-merge/merge-assincrono', {
      repositorio: repositorio.value,
      pull_request: Number(pullRequest.value),
      sha_esperado: pr.value.sha,
      metodo: metodo.value,
      acao: acao.value,
      titulo_commit: tituloCommit.value,
      mensagem_commit: mensagemCommit.value,
    })
    resultado.value = response.data.data
    mensagem.value = 'Solicitação aceita. A proteção do GitHub continuará validando a elegibilidade do integração de alterações.'
    confirmado.value = false
  } catch (error) {
    erro.value = detalheErro(error)
  } finally {
    executando.value = false
  }
}
</script>

<style scoped>
.merge-console { max-width: 1180px; margin: 0 auto; padding: 24px; }
.merge-details { display: grid; gap: 12px; }
.merge-details div { display: grid; grid-template-columns: minmax(120px, 180px) 1fr; gap: 12px; }
.merge-details dt { font-weight: 700; }
.merge-details dd { margin: 0; overflow-wrap: anywhere; }
.resultado-json { overflow: auto; padding: 16px; border-radius: 8px; background: rgba(0, 0, 0, 0.2); }
@media (max-width: 600px) {
  .merge-console { padding: 16px; }
  .merge-details div { grid-template-columns: 1fr; gap: 4px; }
}
</style>
