<template>
  <v-container fluid class="pa-4" data-testid="route-wsjf-planner-excel-installer">
    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-4">
      <div>
        <h1 class="text-h5 font-weight-bold">Instalar Planner → Excel WSJF</h1>
        <p class="text-body-2 text-medium-emphasis mb-0">
          Escolha o ambiente de desenvolvimento, o Planner e o arquivo WSJF.xlsx. O ReqSys resolve os identificadores e instala um único fluxo.
        </p>
      </div>
      <v-chip :color="prontoParaValidar ? 'success' : 'warning'" variant="tonal">
        {{ prontoParaValidar ? 'Pronto para validar' : 'Configuração incompleta' }}
      </v-chip>
    </div>

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4" closable @click:close="erro = ''">
      {{ erro }}
    </v-alert>

    <v-alert v-if="resultado?.dispatched" type="success" variant="tonal" class="mb-4">
      Instalação solicitada. O fluxo será criado inicialmente parado.
      <strong v-if="resultado.correlation_id"> Referência: {{ resultado.correlation_id }}.</strong>
      <a v-if="resultado.workflow_url" :href="resultado.workflow_url" target="_blank" rel="noopener">Acompanhar execução</a>
    </v-alert>

    <v-row>
      <v-col cols="12" lg="7">
        <v-card variant="outlined" class="mb-4">
          <v-card-title class="d-flex align-center ga-2">
            <v-avatar size="28" color="primary">1</v-avatar>
            Ambiente de desenvolvimento
          </v-card-title>
          <v-card-text>
            <v-alert :type="status.microsoft_configurado ? 'success' : 'warning'" variant="tonal" density="compact" class="mb-3">
              {{ status.microsoft_configurado
                ? 'Identidade Microsoft do ReqSys disponível para descoberta.'
                : 'O ReqSys ainda não possui identidade Microsoft configurada neste ambiente.' }}
            </v-alert>

            <v-alert v-if="status.microsoft_configurado && carregado && !ambientesDev.length" type="warning" variant="tonal" density="compact" class="mb-3">
              Nenhum ambiente de desenvolvimento foi encontrado. A tela não libera homologação ou produção.
            </v-alert>

            <v-select
              v-model="ambiente"
              :items="ambientesDev"
              item-title="nome"
              return-object
              label="Ambiente Power Platform de desenvolvimento"
              variant="outlined"
              :disabled="!status.microsoft_configurado"
              @update:model-value="carregarConexoes"
            >
              <template #item="{ props, item }">
                <v-list-item v-bind="props" :subtitle="item.raw?.url || item.raw?.id" />
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
                <v-list-item v-bind="props" :subtitle="item.raw?.email || item.raw?.id" />
              </template>
            </v-select>

            <v-select
              v-model="plano"
              :items="planos"
              item-title="titulo"
              return-object
              label="Planner WSJF"
              variant="outlined"
              :disabled="!grupo"
              @update:model-value="invalidarValidacao"
            />
          </v-card-text>
        </v-card>

        <v-card variant="outlined" class="mb-4">
          <v-card-title class="d-flex align-center ga-2">
            <v-avatar size="28" color="primary">3</v-avatar>
            WSJF.xlsx
          </v-card-title>
          <v-card-text>
            <v-alert v-if="grupo && !carregandoGrupo && !arquivosWsjf.length" type="warning" variant="tonal" density="compact" class="mb-3">
              O arquivo <strong>WSJF.xlsx</strong> não foi encontrado no SharePoint deste grupo. Envie o arquivo para o SharePoint e clique em Atualizar.
            </v-alert>

            <v-select
              v-model="arquivo"
              :items="arquivosWsjf"
              item-title="nome"
              return-object
              label="Planilha WSJF"
              variant="outlined"
              :disabled="!grupo || !arquivosWsjf.length"
              @update:model-value="invalidarValidacao"
            >
              <template #item="{ props, item }">
                <v-list-item v-bind="props" subtitle="Tabela esperada: tbDemandas" />
              </template>
            </v-select>

            <div class="d-flex flex-wrap ga-2">
              <v-btn variant="outlined" prepend-icon="mdi-refresh" :disabled="!grupo" :loading="carregandoGrupo" @click="carregarGrupo">
                Atualizar
              </v-btn>
              <v-btn v-if="arquivo?.web_url" variant="text" prepend-icon="mdi-open-in-new" :href="arquivo.web_url" target="_blank" rel="noopener">
                Abrir WSJF.xlsx
              </v-btn>
            </div>
          </v-card-text>
        </v-card>

        <v-card variant="outlined" class="mb-4">
          <v-card-title class="d-flex align-center ga-2">
            <v-avatar size="28" color="primary">4</v-avatar>
            Conexões Microsoft
          </v-card-title>
          <v-card-text>
            <v-alert v-if="ambiente && (!conexoes.planner.length || !conexoes.excel.length)" type="warning" variant="tonal" density="compact" class="mb-3">
              Falta autorizar {{ !conexoes.planner.length ? 'Planner' : '' }}{{ !conexoes.planner.length && !conexoes.excel.length ? ' e ' : '' }}{{ !conexoes.excel.length ? 'Excel Online (Business)' : '' }} no Power Automate deste ambiente.
            </v-alert>

            <v-row dense>
              <v-col cols="12" md="6">
                <v-select v-model="plannerConnection" :items="conexoes.planner" item-title="nome" return-object label="Planner" variant="outlined" @update:model-value="invalidarValidacao" />
              </v-col>
              <v-col cols="12" md="6">
                <v-select v-model="excelConnection" :items="conexoes.excel" item-title="nome" return-object label="Excel Online (Business)" variant="outlined" @update:model-value="invalidarValidacao" />
              </v-col>
            </v-row>

            <div class="d-flex flex-wrap ga-2">
              <v-btn variant="outlined" prepend-icon="mdi-refresh" :disabled="!ambiente" :loading="carregandoConexoes" @click="carregarConexoes">
                Atualizar conexões
              </v-btn>
              <v-btn variant="text" prepend-icon="mdi-open-in-new" href="https://make.powerautomate.com" target="_blank" rel="noopener">
                Abrir Power Automate
              </v-btn>
            </div>
          </v-card-text>
        </v-card>

        <v-card variant="outlined">
          <v-card-title class="d-flex align-center ga-2">
            <v-avatar size="28" color="primary">5</v-avatar>
            Validar e instalar
          </v-card-title>
          <v-card-text>
            <v-alert type="info" variant="tonal" density="compact" class="mb-3">
              O ReqSys instalará somente <strong>1 fluxo: Planner → tbDemandas</strong>, com recorrência de 1 hora e sem escrita de volta no Planner.
            </v-alert>

            <v-alert v-if="validacao" type="success" variant="tonal" density="compact" class="mb-3">
              Validação aprovada: perfil <strong>{{ validacao.profile }}</strong>, {{ validacao.flows?.length || 0 }} fluxo e tabela <strong>{{ validacao.excel?.table || contrato.excel_table || 'tbDemandas' }}</strong>.
            </v-alert>

            <v-checkbox v-model="confirmado" label="Confirmo a instalação deste fluxo somente no ambiente de desenvolvimento" :disabled="!validacao" />

            <div class="d-flex flex-wrap ga-2">
              <v-btn variant="outlined" :disabled="!prontoParaValidar" :loading="validando" @click="validar">Validar</v-btn>
              <v-btn color="primary" prepend-icon="mdi-rocket-launch" :disabled="!prontoParaInstalar" :loading="implantando" @click="instalar">Instalar fluxo</v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="5">
        <v-card variant="outlined" class="mb-4">
          <v-card-title>Resumo da conexão</v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item title="Ambiente" :subtitle="ambiente?.nome || 'Não escolhido'" />
              <v-list-item title="Grupo Microsoft 365" :subtitle="grupo?.nome || 'Não escolhido'" />
              <v-list-item title="Planner" :subtitle="plano?.titulo || 'Não escolhido'" />
              <v-list-item title="Excel" :subtitle="arquivo?.nome || 'WSJF.xlsx não selecionado'" />
              <v-list-item title="Tabela" :subtitle="contrato.excel_table || 'tbDemandas'" />
              <v-list-item title="Conexão Planner" :subtitle="plannerConnection ? 'Conectada' : 'Pendente'" />
              <v-list-item title="Conexão Excel" :subtitle="excelConnection ? 'Conectada' : 'Pendente'" />
              <v-list-item title="Fluxos" subtitle="1 — Planner → Excel" />
            </v-list>
          </v-card-text>
        </v-card>

        <v-card variant="outlined">
          <v-card-title>O que será preservado</v-card-title>
          <v-card-text>
            <v-chip v-for="campo in camposLocais" :key="campo" size="small" variant="tonal" class="mr-2 mb-2">{{ campo }}</v-chip>
            <p class="text-body-2 text-medium-emphasis mb-0">
              Alterações do Planner atualizam os campos sincronizados, mas não substituem estes campos preenchidos diretamente no Excel.
            </p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  carregarContratoWsjf,
  carregarStatusInstalacao,
  instalarWsjfPlannerExcel,
  listarArquivosInstalacao,
  listarConexoesInstalacao,
  listarGruposInstalacao,
  listarPlanosInstalacao,
  mensagemErroInstalacao,
  somenteAmbientesDev,
  somenteArquivoWsjf,
  validarWsjfPlannerExcel,
} from '../services/wsjfPlannerExcelInstaller'

const status = ref({ ambientes: [], microsoft_configurado: false, alm_configurado: false })
const contrato = ref({})
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
const validacao = ref(null)
const resultado = ref(null)
const confirmado = ref(false)
const erro = ref('')
const carregado = ref(false)
const carregandoGrupo = ref(false)
const carregandoConexoes = ref(false)
const validando = ref(false)
const implantando = ref(false)

const ambientesDev = computed(() => somenteAmbientesDev(status.value.ambientes || []))
const arquivosWsjf = computed(() => somenteArquivoWsjf(arquivos.value))
const camposLocais = computed(() => contrato.value.local_fields_preserved || [
  'Bloqueado',
  'Descrição do bloqueio',
  'Próxima ação',
  'Risco',
  'Observações',
])

const prontoParaValidar = computed(() => Boolean(
  ambiente.value?.id && ambiente.value?.url && grupo.value?.id && plano.value?.id &&
  arquivo.value?.id && arquivo.value?.drive_id && plannerConnection.value?.id &&
  excelConnection.value?.id,
))

const prontoParaInstalar = computed(() => Boolean(
  prontoParaValidar.value && confirmado.value && validacao.value?.profile === 'wsjf_planner_excel_simples',
))

function autoSelecionar(lista, alvo) {
  if (lista.length === 1) alvo.value = lista[0]
}

function invalidarValidacao() {
  validacao.value = null
  resultado.value = null
  confirmado.value = false
}

async function carregarBase() {
  erro.value = ''
  try {
    const [s, g, c] = await Promise.all([
      carregarStatusInstalacao(),
      listarGruposInstalacao(),
      carregarContratoWsjf(),
    ])
    status.value = s
    grupos.value = g.grupos || []
    contrato.value = c || {}
    autoSelecionar(ambientesDev.value, ambiente)
    autoSelecionar(grupos.value, grupo)
    if (ambiente.value) await carregarConexoes()
    if (grupo.value) await carregarGrupo()
  } catch (e) {
    erro.value = mensagemErroInstalacao(e)
  } finally {
    carregado.value = true
  }
}

async function carregarGrupo() {
  invalidarValidacao()
  plano.value = null
  arquivo.value = null
  planos.value = []
  arquivos.value = []
  if (!grupo.value) return
  carregandoGrupo.value = true
  erro.value = ''
  try {
    const [p, a] = await Promise.all([
      listarPlanosInstalacao(grupo.value.id),
      listarArquivosInstalacao(grupo.value.id),
    ])
    planos.value = p.planos || []
    arquivos.value = a.arquivos || []
    autoSelecionar(planos.value, plano)
    autoSelecionar(arquivosWsjf.value, arquivo)
  } catch (e) {
    erro.value = mensagemErroInstalacao(e)
  } finally {
    carregandoGrupo.value = false
  }
}

async function carregarConexoes() {
  invalidarValidacao()
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
    // O backend responde 200 mesmo quando a descoberta falhou (token
    // delegado rejeitado, escopo insuficiente, etc.) e carrega o motivo em
    // c.erro. Sem isto, uma falha real ficava indistinguivel de "conexoes
    // genuinamente nao autorizadas ainda" — mesmo alerta generico nos dois
    // casos.
    if (c.erro) erro.value = c.erro
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
  resultado.value = null
  confirmado.value = false
  try {
    const resposta = await validarWsjfPlannerExcel(payload())
    if (resposta.profile !== 'wsjf_planner_excel_simples' || resposta.flows?.length !== 1) {
      throw new Error('O ReqSys retornou uma configuração diferente da instalação WSJF simples esperada.')
    }
    validacao.value = resposta
  } catch (e) {
    erro.value = mensagemErroInstalacao(e)
  } finally {
    validando.value = false
  }
}

async function instalar() {
  implantando.value = true
  erro.value = ''
  resultado.value = null
  try {
    resultado.value = await instalarWsjfPlannerExcel(payload())
  } catch (e) {
    erro.value = mensagemErroInstalacao(e)
  } finally {
    implantando.value = false
  }
}

onMounted(carregarBase)
</script>
