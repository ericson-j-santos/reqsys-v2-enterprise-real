<template>
  <div class="hub-page">
    <!-- Header -->
    <div class="page-header">
      <div>
        <div class="text-h5 font-weight-bold mb-1">Hub Low-Code & IA</div>
        <div class="text-body-2 text-medium-emphasis">
          Pacotes de contexto IA, flows Power Automate, bot ReqSysAgent e pipelines GitHub ALM.
        </div>
      </div>
      <div class="page-actions">
        <v-btn variant="outlined" prepend-icon="mdi-refresh" :loading="carregando" @click="carregarTudo">
          Atualizar
        </v-btn>
      </div>
    </div>

    <v-alert v-if="erroGlobal" type="warning" variant="tonal" class="mb-4" closable @click:close="erroGlobal = ''">
      {{ erroGlobal }}
    </v-alert>

    <!-- Cards de resumo -->
    <v-row>
      <v-col cols="12" sm="6" lg="3">
        <v-card rounded="xl" elevation="1">
          <v-card-text class="pa-5">
            <div class="d-flex align-center justify-space-between mb-3">
              <v-icon color="primary" size="28">mdi-package-variant-closed</v-icon>
              <v-chip size="x-small" color="primary" variant="tonal">OneDrive → SP</v-chip>
            </div>
            <div class="text-h4 font-weight-bold text-primary">{{ totalPacotes }}</div>
            <div class="text-body-2 text-medium-emphasis mt-1">Pacotes IA exportados</div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" lg="3">
        <v-card rounded="xl" elevation="1">
          <v-card-text class="pa-5">
            <div class="d-flex align-center justify-space-between mb-3">
              <v-icon color="success" size="28">mdi-calendar-clock</v-icon>
              <v-chip size="x-small" :color="chipCorPacote" variant="tonal">{{ labelUltimoPacote }}</v-chip>
            </div>
            <div class="text-h6 font-weight-bold text-success text-truncate">{{ ultimoPacoteProjeto }}</div>
            <div class="text-body-2 text-medium-emphasis mt-1">Último pacote exportado</div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" lg="3">
        <v-card rounded="xl" elevation="1">
          <v-card-text class="pa-5">
            <div class="d-flex align-center justify-space-between mb-3">
              <v-icon color="info" size="28">mdi-robot-outline</v-icon>
              <v-chip size="x-small" color="info" variant="tonal">Copilot Studio</v-chip>
            </div>
            <div class="text-h6 font-weight-bold text-info">ReqSysAgent</div>
            <div class="text-body-2 text-medium-emphasis mt-1">Bot publicado · Planner</div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" lg="3">
        <v-card rounded="xl" elevation="1">
          <v-card-text class="pa-5">
            <div class="d-flex align-center justify-space-between mb-3">
              <v-icon color="warning" size="28">mdi-pipe</v-icon>
              <v-chip size="x-small" :color="chipCorGithub" variant="tonal">{{ labelUltimoRun }}</v-chip>
            </div>
            <div class="text-h6 font-weight-bold text-warning text-truncate">{{ ultimoRunNome }}</div>
            <div class="text-body-2 text-medium-emphasis mt-1">Último run GitHub ALM</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Seção: Pacotes IA -->
    <v-card rounded="xl" elevation="1" class="panel-card mt-2">
      <v-card-title class="pa-5 pb-2 d-flex align-center justify-space-between">
        <div class="d-flex align-center ga-2">
          <v-icon color="primary">mdi-folder-sync-outline</v-icon>
          Pacotes IA Exportados
          <v-chip size="x-small" variant="tonal" color="primary">SharePoint List</v-chip>
        </div>
        <v-chip v-if="!pacotes.configurado" size="small" color="warning" variant="tonal">
          <v-icon start size="small">mdi-alert</v-icon>
          Não configurado
        </v-chip>
      </v-card-title>
      <v-divider />

      <v-alert v-if="pacotes.erro" type="warning" variant="tonal" class="ma-4" density="compact">
        {{ pacotes.erro }}
      </v-alert>

      <v-alert v-if="!pacotes.configurado && !pacotes.erro" type="info" variant="tonal" class="ma-4" density="compact">
        Configure <code>SHAREPOINT_SITE_ID</code>, <code>AZURE_CLIENT_SECRET</code> e
        execute <code>New-IACodigosSync.ps1</code> para ativar o catálogo de pacotes IA.
      </v-alert>

      <v-table v-if="pacotes.itens.length" density="comfortable">
        <thead>
          <tr>
            <th>Projeto</th>
            <th>Branch</th>
            <th>Commit</th>
            <th>Stack</th>
            <th>Arquivos</th>
            <th>Tamanho</th>
            <th>Status</th>
            <th>Exportado em</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in pacotes.itens" :key="p.id">
            <td class="font-weight-medium">{{ p.projeto }}</td>
            <td><code class="text-caption">{{ p.branch }}</code></td>
            <td><code class="text-caption text-mono">{{ p.commit }}</code></td>
            <td>
              <div class="d-flex gap-1 flex-wrap">
                <v-chip v-for="s in (p.tech_stack || '').split(',').filter(Boolean)" :key="s"
                  size="x-small" variant="tonal" color="secondary">
                  {{ s.trim() }}
                </v-chip>
              </div>
            </td>
            <td>{{ p.total_arquivos }}</td>
            <td>{{ p.tamanho_mb }} MB</td>
            <td>
              <v-chip size="x-small" :color="corStatus(p.status)" variant="tonal">{{ p.status }}</v-chip>
            </td>
            <td class="text-caption">{{ formatarData(p.gerado_em) }}</td>
          </tr>
        </tbody>
      </v-table>

      <div v-else-if="pacotes.configurado && !pacotes.erro" class="pa-6 text-center text-medium-emphasis">
        <v-icon size="40" class="mb-2">mdi-package-variant-closed-remove</v-icon>
        <div>Nenhum pacote registrado ainda.</div>
        <div class="text-caption mt-1">Execute <code>exportar-contexto-ia.ps1</code> em algum projeto.</div>
      </div>
    </v-card>

    <!-- Seção: Power Automate -->
    <v-row class="mt-0">
      <v-col cols="12" md="6">
        <v-card rounded="xl" elevation="1" class="panel-card h-100">
          <v-card-title class="pa-5 pb-2 d-flex align-center justify-space-between">
            <div class="d-flex align-center ga-2">
              <v-icon color="info">mdi-electric-switch</v-icon>
              Flows Power Automate
            </div>
            <v-chip v-if="!flows.configurado" size="small" color="warning" variant="tonal">
              Não configurado
            </v-chip>
          </v-card-title>
          <v-divider />

          <v-alert v-if="!flows.configurado" type="info" variant="tonal" class="ma-4" density="compact">
            Configure <code>POWERAUTOMATE_ENV_ID</code> e <code>AZURE_CLIENT_SECRET</code>.
          </v-alert>

          <v-list v-if="flows.flows.length" density="comfortable">
            <v-list-item
              v-for="f in flows.flows"
              :key="f.id"
              :title="f.nome"
              :subtitle="`Modificado: ${formatarData(f.modificado_em)}`"
            >
              <template #prepend>
                <v-icon :color="f.estado === 'Started' ? 'success' : 'grey'">
                  {{ f.estado === 'Started' ? 'mdi-play-circle' : 'mdi-pause-circle' }}
                </v-icon>
              </template>
              <template #append>
                <v-chip size="x-small" :color="f.estado === 'Started' ? 'success' : 'warning'" variant="tonal">
                  {{ f.estado }}
                </v-chip>
              </template>
            </v-list-item>
          </v-list>

          <div v-else-if="flows.configurado" class="pa-4 text-center text-medium-emphasis text-caption">
            Nenhum flow encontrado no ambiente.
          </div>
        </v-card>
      </v-col>

      <!-- Seção: Execuções do flow principal -->
      <v-col cols="12" md="6">
        <v-card rounded="xl" elevation="1" class="panel-card h-100">
          <v-card-title class="pa-5 pb-2 d-flex align-center ga-2">
            <v-icon color="info">mdi-history</v-icon>
            Execuções — Criar no Planner
          </v-card-title>
          <v-divider />

          <v-table v-if="flows.execucoes.length" density="comfortable">
            <thead>
              <tr>
                <th>Status</th>
                <th>Início</th>
                <th>Fim</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="e in flows.execucoes" :key="e.id">
                <td>
                  <v-chip size="x-small" :color="corExecucao(e.status)" variant="tonal">{{ e.status }}</v-chip>
                </td>
                <td class="text-caption">{{ formatarData(e.inicio) }}</td>
                <td class="text-caption">{{ formatarData(e.fim) }}</td>
              </tr>
            </tbody>
          </v-table>

          <div v-else class="pa-4 text-center text-medium-emphasis text-caption">
            {{ flows.configurado ? 'Sem execuções registradas.' : 'Configure POWERAUTOMATE_ENV_ID para ver execuções.' }}
          </div>
        </v-card>
      </v-col>
    </v-row>

    <!-- Seção: GitHub Actions ALM -->
    <v-card rounded="xl" elevation="1" class="panel-card mt-2">
      <v-card-title class="pa-5 pb-2 d-flex align-center justify-space-between">
        <div class="d-flex align-center ga-2">
          <v-icon color="warning">mdi-source-branch</v-icon>
          GitHub Actions — ALM Pipeline
          <v-chip size="x-small" variant="tonal" color="warning">{{ settings.github_alm_repo || 'reqsys-powerplatform-alm' }}</v-chip>
        </div>
        <div class="d-flex align-center ga-2">
          <v-chip v-if="falhasConsecutivas >= 2" size="small" color="error" variant="tonal" prepend-icon="mdi-alert">
            {{ falhasConsecutivas }} falhas seguidas
          </v-chip>
          <v-chip v-if="!github.configurado" size="small" color="warning" variant="tonal">
            Sem token — limite de rate
          </v-chip>
        </div>
      </v-card-title>
      <v-divider />

      <v-alert
        v-if="falhasConsecutivas >= 3"
        type="error"
        variant="tonal"
        class="ma-4"
        density="compact"
        icon="mdi-pipe-disconnected"
      >
        <strong>{{ falhasConsecutivas }} deploys consecutivos falhando.</strong>
        Causa provável: connection reference <code>new_sharedplanner_e51d2</code> não configurada nos ambientes Test/Prod.
        Execute <code>.\scripts\07-obter-connection-ids.ps1</code> após criar uma conexão Planner em
        <a href="https://make.powerapps.com" target="_blank" class="text-error">make.powerapps.com</a>.
      </v-alert>

      <v-alert v-if="github.erro" type="warning" variant="tonal" class="ma-4" density="compact">
        {{ github.erro }}
      </v-alert>

      <v-table v-if="github.runs.length" density="comfortable">
        <thead>
          <tr>
            <th>Workflow</th>
            <th>Branch</th>
            <th>Commit</th>
            <th>Status</th>
            <th>Conclusão</th>
            <th>Data</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in github.runs" :key="r.id" :class="r.conclusao === 'failure' ? 'row-failure' : ''">
            <td class="text-caption font-weight-medium">{{ r.nome }}</td>
            <td><code class="text-caption">{{ r.branch }}</code></td>
            <td><code class="text-caption">{{ r.commit }}</code></td>
            <td>
              <v-chip size="x-small" :color="corStatusRun(r.status)" variant="tonal">{{ r.status }}</v-chip>
            </td>
            <td>
              <v-chip v-if="r.conclusao" size="x-small" :color="corConclusao(r.conclusao)" variant="tonal">
                {{ r.conclusao }}
              </v-chip>
              <span v-else class="text-caption text-medium-emphasis">—</span>
            </td>
            <td class="text-caption">{{ formatarData(r.criado_em) }}</td>
            <td>
              <v-btn
                v-if="r.url"
                :href="r.url"
                target="_blank"
                size="x-small"
                variant="text"
                icon="mdi-open-in-new"
                :color="r.conclusao === 'failure' ? 'error' : 'grey'"
              />
            </td>
          </tr>
        </tbody>
      </v-table>

      <div v-else-if="!github.erro" class="pa-6 text-center text-medium-emphasis">
        <v-icon size="36" class="mb-2">mdi-github</v-icon>
        <div class="text-caption">Configure <code>GITHUB_PAT</code> para evitar limite de rate da API pública.</div>
      </div>
    </v-card>

    <!-- Seção: Padrão Ouro — instruções rápidas -->
    <v-card rounded="xl" elevation="1" class="panel-card mt-2">
      <v-card-title class="pa-5 pb-2 d-flex align-center ga-2">
        <v-icon color="success">mdi-star-circle-outline</v-icon>
        Padrão Ouro — Como exportar um pacote IA
      </v-card-title>
      <v-divider />
      <v-card-text>
        <v-row>
          <v-col cols="12" md="4">
            <div class="text-subtitle-2 font-weight-bold mb-2">
              <v-icon size="18" color="primary" class="mr-1">mdi-numeric-1-circle</v-icon>
              Exportação manual
            </div>
            <v-code tag="pre" class="text-caption pa-3" style="white-space: pre-wrap; background: rgb(var(--v-theme-surface-variant));">.\exportar-contexto-ia.ps1 `
  -NomeProjeto "reqsys"</v-code>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-subtitle-2 font-weight-bold mb-2">
              <v-icon size="18" color="warning" class="mr-1">mdi-numeric-2-circle</v-icon>
              Git hook (pós-commit)
            </div>
            <v-code tag="pre" class="text-caption pa-3" style="white-space: pre-wrap; background: rgb(var(--v-theme-surface-variant));">#!/bin/sh
powershell.exe -ExecutionPolicy Bypass \
  -File tools/exportar-contexto-ia.ps1 \
  -NomeProjeto "reqsys"</v-code>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-subtitle-2 font-weight-bold mb-2">
              <v-icon size="18" color="success" class="mr-1">mdi-numeric-3-circle</v-icon>
              Fluxo completo
            </div>
            <v-list density="compact" class="pa-0">
              <v-list-item density="compact" prepend-icon="mdi-git" title="Commit no Git" />
              <v-list-item density="compact" prepend-icon="mdi-script-text" title="Script exporta pacote" />
              <v-list-item density="compact" prepend-icon="mdi-microsoft-onedrive" title="OneDrive sincroniza" />
              <v-list-item density="compact" prepend-icon="mdi-electric-switch" title="Power Automate indexa" />
              <v-list-item density="compact" prepend-icon="mdi-robot" title="IA consome o contexto" />
            </v-list>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'

const carregando = ref(false)
const erroGlobal = ref('')

const pacotes = ref({ configurado: false, itens: [], erro: null })
const flows = ref({ configurado: false, flows: [], execucoes: [], erro: null })
const github = ref({ configurado: false, runs: [], erro: null })
const settings = ref({ github_alm_repo: '' })

// --- Computeds de resumo ---

const totalPacotes = computed(() => pacotes.value.itens.length || '—')

const ultimoPacoteProjeto = computed(() => pacotes.value.itens[0]?.projeto || '—')
const labelUltimoPacote = computed(() => {
  const d = pacotes.value.itens[0]?.gerado_em
  if (!d) return 'Nenhum'
  return formatarData(d).split(' ')[0]
})
const chipCorPacote = computed(() => pacotes.value.itens.length ? 'success' : 'grey')

const ultimoRunNome = computed(() => github.value.runs[0]?.nome || '—')
const labelUltimoRun = computed(() => {
  const r = github.value.runs[0]
  if (!r) return 'Nenhum'
  return r.conclusao || r.status || '—'
})
const chipCorGithub = computed(() => corConclusao(github.value.runs[0]?.conclusao))

const falhasConsecutivas = computed(() => {
  let count = 0
  for (const r of github.value.runs) {
    if (r.conclusao === 'failure') count++
    else break
  }
  return count
})

// --- Helpers de cor ---

function corStatus(status) {
  if (!status) return 'grey'
  const s = status.toLowerCase()
  if (s === 'processado') return 'success'
  if (s === 'pendente') return 'warning'
  if (s === 'erro') return 'error'
  if (s === 'duplicado') return 'info'
  return 'grey'
}

function corExecucao(status) {
  if (!status) return 'grey'
  const s = status.toLowerCase()
  if (s === 'succeeded') return 'success'
  if (s === 'running') return 'info'
  if (s === 'failed') return 'error'
  return 'grey'
}

function corStatusRun(status) {
  if (!status) return 'grey'
  if (status === 'completed') return 'success'
  if (status === 'in_progress') return 'info'
  if (status === 'queued') return 'warning'
  return 'grey'
}

function corConclusao(conclusao) {
  if (!conclusao) return 'grey'
  if (conclusao === 'success') return 'success'
  if (conclusao === 'failure') return 'error'
  if (conclusao === 'cancelled') return 'warning'
  if (conclusao === 'skipped') return 'grey'
  return 'info'
}

function formatarData(raw) {
  if (!raw) return '—'
  const d = new Date(raw)
  if (isNaN(d.getTime())) return raw
  return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

// --- Carga de dados ---

async function carregarPacotes() {
  try {
    const { data } = await api.get('/v1/hub-lowcode/pacotes')
    pacotes.value = data.data ?? data
  } catch {
    pacotes.value = { configurado: false, itens: [], erro: 'Erro ao carregar pacotes IA.' }
  }
}

async function carregarFlows() {
  try {
    const { data } = await api.get('/v1/hub-lowcode/flows')
    flows.value = data.data ?? data
  } catch {
    flows.value = { configurado: false, flows: [], execucoes: [], erro: 'Erro ao carregar flows.' }
  }
}

async function carregarGithub() {
  try {
    const { data } = await api.get('/v1/hub-lowcode/github')
    github.value = data.data ?? data
  } catch {
    github.value = { configurado: false, runs: [], erro: 'Erro ao carregar GitHub Actions.' }
  }
}

async function carregarTudo() {
  carregando.value = true
  erroGlobal.value = ''
  await Promise.all([carregarPacotes(), carregarFlows(), carregarGithub()])
  carregando.value = false
}

onMounted(carregarTudo)
</script>

<style scoped>
.hub-page {
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
  align-items: center;
}

.panel-card {
  border: 1px solid rgba(208, 208, 208, 0.9);
}

.text-mono {
  font-family: monospace;
}

.row-failure td {
  background-color: rgba(var(--v-theme-error), 0.04);
}
</style>
