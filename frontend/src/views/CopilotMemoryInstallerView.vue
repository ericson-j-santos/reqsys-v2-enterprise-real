<template>
  <v-container fluid class="pa-4" data-testid="route-copilot-memory-installer">
    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-4">
      <div>
        <h1 class="text-h5 font-weight-bold">Instalar Copilot Memory</h1>
        <p class="text-body-2 text-medium-emphasis mb-0">
          Escolha o ambiente, o Planner e a planilha. O ReqSys prepara e instala os três fluxos.
        </p>
      </div>
      <v-chip :color="prontoParaImplantar ? 'success' : 'warning'" variant="tonal">
        {{ prontoParaImplantar ? 'Pronto para instalar' : 'Configuração incompleta' }}
      </v-chip>
    </div>

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4" closable @click:close="erro = ''">
      {{ erro }}
    </v-alert>
    <v-alert v-if="resultado?.dispatched" type="success" variant="tonal" class="mb-4">
      Instalação solicitada. Correlation ID: <strong>{{ resultado.correlation_id }}</strong>.
      <a v-if="resultado.workflow_url" :href="resultado.workflow_url" target="_blank" rel="noopener">Acompanhar execução</a>
    </v-alert>

    <v-row>
      <v-col cols="12" lg="7">
        <v-card variant="outlined" class="mb-4">
          <v-card-title class="d-flex align-center ga-2">
            <v-avatar size="28" color="primary">1</v-avatar>
            Ambiente Microsoft 365
          </v-card-title>
          <v-card-text>
            <v-alert
              :type="status.microsoft_configurado ? 'success' : 'warning'"
              variant="tonal"
              density="compact"
              class="mb-3"
            >
              {{ status.microsoft_configurado
                ? 'Conexão corporativa do ReqSys disponível.'
                : 'A instalação automática ainda não possui uma identidade Microsoft autorizada neste ambiente.' }}
            </v-alert>
            <v-alert v-if="!status.microsoft_configurado" type="info" variant="tonal" density="compact" class="mb-3">
              A contingência continua disponível: baixe a solução nativa e importe em Power Automate → Soluções → Importar.
            </v-alert>
            <v-select
              v-model="ambiente"
              :items="status.ambientes || []"
              item-title="nome"
              return-object
              label="Ambiente Power Platform"
              variant="outlined"
              :disabled="!status.microsoft_configurado"
              @update:model-value="carregarConexoes"
            >
              <template #item="{ props, item }">
                <v-list-item v-bind="props" :subtitle="item.raw.url || item.raw.id" />
              </template>
            </v-select>
          </v-card-text>
        </v-card>

        <v-card variant="outlined" class="mb-4">
          <v-card-title class="d-flex align-center ga-2">
            <v-avatar size="28" color="primary">2</v-avatar>
            Planner
          </v-card-title>
          <v-card-text>
            <v-select
              v-model="grupo"
              :items="grupos"
              item-title="nome"
              return-object
              label="Grupo ou equipe Microsoft 365"
              variant="outlined"
              :disabled="!ambiente"
              @update:model-value="carregarGrupo"
            >
              <template #item="{ props, item }">
                <v-list-item v-bind="props" :subtitle="item.raw.email" />
              </template>
            </v-select>
            <v-select
              v-model="plano"
              :items="planos"
              item-title="titulo"
              return-object
              label="Plano do Planner"
              variant="outlined"
              :disabled="!grupo"
            />
          </v-card-text>
        </v-card>

        <v-card variant="outlined" class="mb-4">
          <v-card-title class="d-flex align-center ga-2">
            <v-avatar size="28" color="primary">3</v-avatar>
            Memória no Excel
          </v-card-title>
          <v-card-text>
            <v-select
              v-model="arquivo"
              :items="arquivos"
              item-title="nome"
              return-object
              label="Planilha"
              variant="outlined"
              :disabled="!grupo"
            />
            <div class="d-flex flex-wrap ga-2">
              <v-btn
                color="primary"
                variant="tonal"
                prepend-icon="mdi-file-excel"
                :disabled="!grupo"
                :loading="criandoPlanilha"
                @click="criarPlanilha"
              >
                Criar CopilotMemory.xlsx automaticamente
              </v-btn>
              <v-btn variant="text" :disabled="!grupo" @click="carregarArquivos">
                Atualizar lista
              </v-btn>
            </div>
          </v-card-text>
        </v-card>

        <v-card variant="outlined" class="mb-4">
          <v-card-title class="d-flex align-center ga-2">
            <v-avatar size="28" color="primary">4</v-avatar>
            Conexões
          </v-card-title>
          <v-card-text>
            <v-alert v-if="ambiente && (!conexoes.planner.length || !conexoes.excel.length)" type="warning" variant="tonal" density="compact" class="mb-3">
              Falta autorizar {{ !conexoes.planner.length ? 'Planner' : '' }}{{ !conexoes.planner.length && !conexoes.excel.length ? ' e ' : '' }}{{ !conexoes.excel.length ? 'Excel Online (Business)' : '' }}.
              Crie a conexão no Power Automate e clique em Atualizar conexões.
            </v-alert>
            <v-row dense>
              <v-col cols="12" md="6">
                <v-select v-model="plannerConnection" :items="conexoes.planner" item-title="nome" return-object label="Conexão Planner" variant="outlined" />
              </v-col>
              <v-col cols="12" md="6">
                <v-select v-model="excelConnection" :items="conexoes.excel" item-title="nome" return-object label="Conexão Excel" variant="outlined" />
              </v-col>
            </v-row>
            <div class="d-flex flex-wrap ga-2">
              <v-btn variant="outlined" prepend-icon="mdi-refresh" :disabled="!ambiente" :loading="carregandoConexoes" @click="carregarConexoes">
                Atualizar conexões
              </v-btn>
              <v-btn variant="text" prepend-icon="mdi-open-in-new" href="https://make.powerautomate.com" target="_blank" rel="noopener">
                Autorizar no Power Automate
              </v-btn>
            </div>
          </v-card-text>
        </v-card>

        <v-card variant="outlined">
          <v-card-title class="d-flex align-center ga-2">
            <v-avatar size="28" color="primary">5</v-avatar>
            Instalar
          </v-card-title>
          <v-card-text>
            <v-alert type="info" variant="tonal" density="compact" class="mb-3">
              A instalação cria três fluxos: Planner → memória, memória → Planner e verificação de saúde. Produção não é selecionada automaticamente.
            </v-alert>
            <v-checkbox v-model="confirmado" label="Confirmo a instalação neste ambiente" :disabled="!prontoParaValidar" />
            <div class="d-flex flex-wrap ga-2">
              <v-btn variant="outlined" :disabled="!prontoParaValidar" :loading="validando" @click="validar">
                Validar instalação
              </v-btn>
              <v-btn color="primary" :disabled="!prontoParaImplantar" :loading="implantando" prepend-icon="mdi-rocket-launch" @click="implantar">
                Instalar 3 fluxos
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="5">
        <v-card variant="outlined" class="mb-4" position="sticky">
          <v-card-title>Resumo</v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item title="Microsoft 365" :subtitle="status.microsoft_configurado ? 'Disponível' : 'Pendente para instalação automática'" />
              <v-list-item title="Ambiente" :subtitle="ambiente?.nome || 'Não escolhido'" />
              <v-list-item title="Grupo" :subtitle="grupo?.nome || 'Não escolhido'" />
              <v-list-item title="Planner" :subtitle="plano?.titulo || 'Não escolhido'" />
              <v-list-item title="Planilha" :subtitle="arquivo?.nome || 'Não escolhida'" />
              <v-list-item title="Planner conectado" :subtitle="plannerConnection ? 'Sim' : 'Não'" />
              <v-list-item title="Excel conectado" :subtitle="excelConnection ? 'Sim' : 'Não'" />
              <v-list-item title="Executor ALM" :subtitle="status.alm_configurado ? 'Disponível' : 'Pendente'" />
            </v-list>
            <v-divider class="my-3" />
            <v-alert type="info" variant="tonal" density="compact" class="mb-3">
              Caminho manual independente da configuração acima: importe <strong>CopilotMemoryInstaller.zip</strong> em Soluções.
            </v-alert>
            <v-btn block color="primary" variant="tonal" prepend-icon="mdi-package-variant" :loading="baixandoSolucao" @click="baixarSolucaoManual">
              Baixar solução para importar
            </v-btn>
            <v-btn block class="mt-2" variant="text" prepend-icon="mdi-download" :loading="baixando" @click="baixarContingencia">
              Baixar contingência completa
            </v-btn>
          </v-card-text>
        </v-card>

        <v-alert v-if="validacao" :type="validacao.status === 'aguardando_confirmacao' ? 'success' : 'info'" variant="tonal">
          Estrutura validada. {{ validacao.bundle?.flows?.length || 0 }} fluxos preparados.
        </v-alert>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  baixarPacoteGerado,
  baixarSolucaoNativa,
  carregarStatusInstalacao,
  criarPlanilhaInstalacao,
  gerarPacoteCopilotMemory,
  implantarCopilotMemory,
  listarArquivosInstalacao,
  listarConexoesInstalacao,
  listarGruposInstalacao,
  listarPlanosInstalacao,
  mensagemErroInstalacao,
  validarImplantacao,
} from '../services/copilotMemoryInstaller'

const status = ref({ ambientes: [], microsoft_configurado: false, alm_configurado: false })
const grupos = ref([])
const planos = ref([])
const arquivos = ref([])
const conexoes = ref({ planner: [], excel: [] })
const ambiente = ref(null)
const grupo = ref(null)
const plano = ref(null)
const arquivo = ref(null)
const plannerConnection = ref(null)
const excelConnection = ref(null)
const confirmado = ref(false)
const validacao = ref(null)
const resultado = ref(null)
const erro = ref('')
const criandoPlanilha = ref(false)
const carregandoConexoes = ref(false)
const validando = ref(false)
const implantando = ref(false)
const baixando = ref(false)
const baixandoSolucao = ref(false)

const prontoParaValidar = computed(() => Boolean(
  ambiente.value?.id && ambiente.value?.url && grupo.value?.id && plano.value?.id &&
  arquivo.value?.id && arquivo.value?.drive_id && plannerConnection.value?.id && excelConnection.value?.id &&
  status.value.alm_configurado,
))
const prontoParaImplantar = computed(() => Boolean(prontoParaValidar.value && confirmado.value && validacao.value))

function autoSelecionar(lista, alvo) {
  if (lista.length === 1) alvo.value = lista[0]
}

async function carregarBase() {
  erro.value = ''
  try {
    const [s, g] = await Promise.all([carregarStatusInstalacao(), listarGruposInstalacao()])
    status.value = s
    grupos.value = g.grupos || []
    autoSelecionar(status.value.ambientes || [], ambiente)
    autoSelecionar(grupos.value, grupo)
    if (ambiente.value) await carregarConexoes()
    if (grupo.value) await carregarGrupo()
  } catch (e) {
    erro.value = mensagemErroInstalacao(e)
  }
}

async function carregarGrupo() {
  plano.value = null
  arquivo.value = null
  planos.value = []
  arquivos.value = []
  if (!grupo.value) return
  try {
    const [p, a] = await Promise.all([
      listarPlanosInstalacao(grupo.value.id),
      listarArquivosInstalacao(grupo.value.id),
    ])
    planos.value = p.planos || []
    arquivos.value = a.arquivos || []
    autoSelecionar(planos.value, plano)
    autoSelecionar(arquivos.value.filter((item) => item.nome === 'CopilotMemory.xlsx'), arquivo)
  } catch (e) {
    erro.value = mensagemErroInstalacao(e)
  }
}

async function carregarArquivos() {
  if (!grupo.value) return
  try {
    const a = await listarArquivosInstalacao(grupo.value.id)
    arquivos.value = a.arquivos || []
  } catch (e) {
    erro.value = mensagemErroInstalacao(e)
  }
}

async function criarPlanilha() {
  if (!grupo.value) return
  criandoPlanilha.value = true
  erro.value = ''
  try {
    arquivo.value = await criarPlanilhaInstalacao(grupo.value.id)
    const criadoId = arquivo.value?.id
    await carregarArquivos()
    arquivo.value = arquivos.value.find((item) => item.id === criadoId) || arquivo.value
  } catch (e) {
    erro.value = `${mensagemErroInstalacao(e)} Use o pacote de contingência se a política do tenant bloquear a criação automática.`
  } finally {
    criandoPlanilha.value = false
  }
}

async function carregarConexoes() {
  plannerConnection.value = null
  excelConnection.value = null
  conexoes.value = { planner: [], excel: [] }
  if (!ambiente.value?.id) return
  carregandoConexoes.value = true
  erro.value = ''
  try {
    const c = await listarConexoesInstalacao(ambiente.value.id)
    conexoes.value = { planner: c.planner || [], excel: c.excel || [] }
    autoSelecionar(conexoes.value.planner, plannerConnection)
    autoSelecionar(conexoes.value.excel, excelConnection)
  } catch (e) {
    erro.value = mensagemErroInstalacao(e)
  } finally {
    carregandoConexoes.value = false
  }
}

function payload() {
  return {
    environment_id: ambiente.value.id,
    environment_url: ambiente.value.url,
    group_id: grupo.value.id,
    plan_id: plano.value.id,
    excel_source: arquivo.value.excel_source || `groups/${grupo.value.id}`,
    excel_drive: arquivo.value.drive_id,
    excel_file: arquivo.value.id,
    planner_connection_id: plannerConnection.value.id,
    excel_connection_id: excelConnection.value.id,
    target_environment: 'dev',
  }
}

async function validar() {
  validando.value = true
  erro.value = ''
  validacao.value = null
  try {
    validacao.value = await validarImplantacao(payload())
  } catch (e) {
    erro.value = mensagemErroInstalacao(e)
  } finally {
    validando.value = false
  }
}

async function implantar() {
  implantando.value = true
  erro.value = ''
  resultado.value = null
  try {
    resultado.value = await implantarCopilotMemory(payload())
    if (!resultado.value.dispatched) erro.value = resultado.value.erro || 'A implantação não foi despachada.'
  } catch (e) {
    erro.value = mensagemErroInstalacao(e)
  } finally {
    implantando.value = false
  }
}

async function baixarSolucaoManual() {
  baixandoSolucao.value = true
  erro.value = ''
  try {
    baixarSolucaoNativa(await gerarPacoteCopilotMemory())
  } catch (e) {
    erro.value = mensagemErroInstalacao(e)
  } finally {
    baixandoSolucao.value = false
  }
}

async function baixarContingencia() {
  baixando.value = true
  erro.value = ''
  try {
    baixarPacoteGerado(await gerarPacoteCopilotMemory())
  } catch (e) {
    erro.value = mensagemErroInstalacao(e)
  } finally {
    baixando.value = false
  }
}

onMounted(carregarBase)
</script>