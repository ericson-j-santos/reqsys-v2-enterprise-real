<template>
  <div class="page">
    <!-- Toast container -->
    <div class="toast-container">
      <transition-group name="toast">
        <div
          v-for="t in toast.toasts"
          :key="t.id"
          class="toast-item"
          :class="`toast-${t.type}`"
          @click="toast.remove(t.id)"
        >
          <v-icon size="16" class="mr-1">{{ toastIcon(t.type) }}</v-icon>
          {{ t.msg }}
        </div>
      </transition-group>
    </div>

    <div class="page-header">
      <h1>◈ Pipeline de Requisitos</h1>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;row-gap:6px">
        <v-btn-toggle v-model="nivelFiltro" mandatory density="compact" variant="outlined" color="amber">
          <v-tooltip text="Visão detalhada por step individual" location="top">
            <template #activator="{ props }">
              <v-btn v-bind="props" value="micro" size="small">Micro</v-btn>
            </template>
          </v-tooltip>
          <v-tooltip text="Visão agrupada por categoria de log" location="top">
            <template #activator="{ props }">
              <v-btn v-bind="props" value="macro" size="small">Macro</v-btn>
            </template>
          </v-tooltip>
        </v-btn-toggle>
        <span class="demo-badge" v-if="demoMode">DEMO</span>
        <v-switch
          v-model="demoMode"
          label="Modo demo"
          density="compact"
          hide-details
          color="amber"
          class="mt-0"
        />
        <v-btn
          v-if="correlatioId"
          variant="outlined"
          size="small"
          prepend-icon="mdi-identifier"
          @click="copiarCorrelation"
        >{{ correlatioId.slice(0, 12) }}…</v-btn>
        <v-tooltip v-if="statusOrigemDemanda" text="Status recebido da tela Ver Demanda e aplicado no snapshot inicial dos steps" location="top">
          <template #activator="{ props }">
            <v-chip v-bind="props" size="small" :color="statusOrigemColor(statusOrigemDemanda)" variant="flat" prepend-icon="mdi-source-branch">
              Origem: {{ statusOrigemLabel(statusOrigemDemanda) }}
            </v-chip>
          </template>
        </v-tooltip>
        <v-tooltip v-if="statusOrigemDemanda" text="Remove o contexto importado e volta os steps para estado neutro" location="top">
          <template #activator="{ props }">
            <v-btn v-bind="props" size="small" variant="text" prepend-icon="mdi-close-circle-outline" @click="limparContextoOrigem">
              Limpar contexto
            </v-btn>
          </template>
        </v-tooltip>
      </div>
    </div>

    <!-- Step indicator -->
    <v-card class="mb-5 pa-4" style="background:var(--card)!important;border:1px solid var(--border)!important">
      <div
        v-if="statusOrigemDemanda && snapshotAplicado"
        style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:10px;padding:8px 10px;border:1px solid var(--border);border-radius:8px;background:#1b2536"
      >
        <div style="display:flex;align-items:center;gap:6px;color:#cbd5e1;font-size:12px">
          <v-icon size="15" color="amber">mdi-timeline-check-outline</v-icon>
          Snapshot inicial aplicado a partir do status {{ statusOrigemLabel(statusOrigemDemanda) }}
        </div>
        <v-tooltip text="Ao clicar em Executar Pipeline, o fluxo roda normalmente e recalcula os steps em tempo real" location="top">
          <template #activator="{ props }">
            <v-chip v-bind="props" size="x-small" color="amber" variant="outlined">Snapshot ativo</v-chip>
          </template>
        </v-tooltip>
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:10px">
        <div style="font-size:11px;color:var(--muted);display:flex;align-items:center;gap:6px">
          <v-icon size="14" color="grey">mdi-information-outline</v-icon>
          Legenda de status da demanda (clique para simular)
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <v-tooltip text="Entrada inicial da demanda" location="top">
            <template #activator="{ props }">
              <v-chip
                v-bind="props"
                size="x-small"
                color="blue"
                :variant="isLegendaAtiva('recebido') ? 'flat' : 'outlined'"
                @click="toggleLegendaStatus('recebido')"
              >Recebido</v-chip>
            </template>
          </v-tooltip>
          <v-tooltip text="Demanda em análise funcional/técnica" location="top">
            <template #activator="{ props }">
              <v-chip
                v-bind="props"
                size="x-small"
                color="orange"
                :variant="isLegendaAtiva('em_analise') ? 'flat' : 'outlined'"
                @click="toggleLegendaStatus('em_analise')"
              >Em análise</v-chip>
            </template>
          </v-tooltip>
          <v-tooltip text="Aprovada para seguir no fluxo" location="top">
            <template #activator="{ props }">
              <v-chip
                v-bind="props"
                size="x-small"
                color="green"
                :variant="isLegendaAtiva('aprovado') ? 'flat' : 'outlined'"
                @click="toggleLegendaStatus('aprovado')"
              >Aprovado</v-chip>
            </template>
          </v-tooltip>
          <v-tooltip text="Interrompida por reprovação ou inconsistência" location="top">
            <template #activator="{ props }">
              <v-chip
                v-bind="props"
                size="x-small"
                color="red"
                :variant="isLegendaAtiva('rejeitado') ? 'flat' : 'outlined'"
                @click="toggleLegendaStatus('rejeitado')"
              >Rejeitado</v-chip>
            </template>
          </v-tooltip>
          <v-tooltip text="Publicada no destino final (ex.: Redmine)" location="top">
            <template #activator="{ props }">
              <v-chip
                v-bind="props"
                size="x-small"
                color="teal"
                :variant="isLegendaAtiva('publicado') ? 'flat' : 'outlined'"
                @click="toggleLegendaStatus('publicado')"
              >Publicado</v-chip>
            </template>
          </v-tooltip>
        </div>
      </div>
      <div class="steps-bar">
        <div
          v-for="(step, idx) in steps"
          :key="step.key"
          class="step-item"
          :class="{
            'step-done':    step.status === 'ok',
            'step-error':   step.status === 'error',
            'step-warn':    step.status === 'warn',
            'step-running': step.status === 'running',
            'step-active':  currentStep === idx && step.status === 'idle'
          }"
        >
          <div class="step-badge">
            <v-progress-circular v-if="step.status === 'running'" indeterminate size="16" width="2" color="amber" />
            <v-icon v-else size="16">{{ stepIcon(step.status) }}</v-icon>
          </div>
          <div class="step-label">{{ step.label }}</div>
          <div class="step-connector" v-if="idx < steps.length - 1" />
        </div>
      </div>
    </v-card>

    <v-row align="start">
      <!-- Formulário -->
      <v-col cols="12" md="5">
        <v-card style="background:var(--card)!important;border:1px solid var(--border)!important">
          <v-card-title class="py-3 px-4" style="font-size:15px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
            Solicitação de Requisito
            <v-tooltip text="Preencha todos os campos obrigatórios (*) e clique em Executar Pipeline" location="top">
              <template #activator="{ props }">
                <v-icon v-bind="props" size="18" color="grey">mdi-information-outline</v-icon>
              </template>
            </v-tooltip>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <v-form ref="formRef" v-model="formValido">

              <!-- Sumário clicável de campos inválidos -->
              <v-alert
                v-if="Object.keys(errosApiCampos).length > 0"
                type="error"
                variant="tonal"
                density="compact"
                class="mb-4"
                icon="mdi-alert-circle-outline"
              >
                <div style="font-weight:600;margin-bottom:6px">Campos com erro — clique para ir ao campo:</div>
                <div style="display:flex;flex-wrap:wrap;gap:6px">
                  <v-chip
                    v-for="campo in Object.keys(errosApiCampos)"
                    :key="campo"
                    size="small"
                    color="error"
                    variant="outlined"
                    style="cursor:pointer"
                    @click="scrollParaCampo(campo)"
                  >
                    {{ labelsCampos[campo] || campo }}
                  </v-chip>
                </div>
              </v-alert>

              <v-tooltip text="Canal de entrada da demanda (e-mail, reunião, sistema externo etc.)" location="top">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-select
                      ref="refOrigem"
                      v-model="form.origem"
                      :items="origens"
                      label="Origem *"
                      variant="outlined"
                      density="compact"
                      class="mb-3"
                      :error="temErroCampo('origem')"
                      :error-messages="mensagemCampo('origem')"
                      :rules="[r => !!r || 'Obrigatório']"
                    />
                  </div>
                </template>
              </v-tooltip>

              <v-tooltip text="Descreva o objetivo da demanda em até 120 caracteres" location="top">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-text-field
                      ref="refTitulo"
                      v-model="form.titulo"
                      label="Título *"
                      variant="outlined"
                      density="compact"
                      class="mb-3"
                      counter="120"
                      :error="temErroCampo('titulo')"
                      :error-messages="mensagemCampo('titulo')"
                      :rules="[
                        r => !!r || 'Obrigatório',
                        r => r.length >= 10 || 'Mínimo 10 caracteres',
                        r => r.length <= 120 || 'Máximo 120 caracteres'
                      ]"
                    />
                  </div>
                </template>
              </v-tooltip>

              <v-tooltip text="Prioridade: crítica (bloqueador), alta (impacto relevante), média, baixa" location="top">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-select
                      ref="refUrgencia"
                      v-model="form.urgencia"
                      :items="urgencias"
                      label="Urgência *"
                      variant="outlined"
                      density="compact"
                      class="mb-3"
                      :error="temErroCampo('urgencia')"
                      :error-messages="mensagemCampo('urgencia')"
                      :rules="[r => !!r || 'Obrigatório']"
                    />
                  </div>
                </template>
              </v-tooltip>

              <v-tooltip text="Descreva o contexto, objetivo e impacto da demanda (20–2000 chars)" location="top">
                <template #activator="{ props }">
                  <div v-bind="props">
                    <v-textarea
                      ref="refDescricao"
                      v-model="form.descricao"
                      label="Descrição *"
                      variant="outlined"
                      density="compact"
                      rows="4"
                      counter="2000"
                      class="mb-3"
                      :error="temErroCampo('descricao')"
                      :error-messages="mensagemCampo('descricao')"
                      :rules="[
                        r => !!r || 'Obrigatório',
                        r => r.length >= 20 || 'Mínimo 20 caracteres',
                        r => r.length <= 2000 || 'Máximo 2000 caracteres'
                      ]"
                    />
                  </div>
                </template>
              </v-tooltip>

              <v-row dense class="mb-1">
                <v-col cols="6">
                  <v-text-field
                    ref="refArea"
                    v-model="form.area"
                    label="Área"
                    variant="outlined"
                    density="compact"
                    :error="temErroCampo('area')"
                    :error-messages="mensagemCampo('area')"
                    :rules="[r => !r || r.length <= 60 || 'Máx 60 chars']"
                  />
                </v-col>
                <v-col cols="6">
                  <v-text-field
                    ref="refSistema"
                    v-model="form.sistema"
                    label="Sistema"
                    variant="outlined"
                    density="compact"
                    :error="temErroCampo('sistema')"
                    :error-messages="mensagemCampo('sistema')"
                  />
                </v-col>
              </v-row>

              <v-row dense class="mb-1">
                <v-col cols="6">
                  <v-text-field
                    ref="refModulo"
                    v-model="form.modulo"
                    label="Módulo"
                    variant="outlined"
                    density="compact"
                    :error="temErroCampo('modulo')"
                    :error-messages="mensagemCampo('modulo')"
                  />
                </v-col>
                <v-col cols="6">
                  <v-text-field
                    ref="refSolicitante"
                    v-model="form.solicitante"
                    label="Solicitante"
                    variant="outlined"
                    density="compact"
                    :error="temErroCampo('solicitante')"
                    :error-messages="mensagemCampo('solicitante')"
                  />
                </v-col>
              </v-row>

              <v-text-field
                ref="refIdExterno"
                v-model="form.id_externo"
                label="ID Externo (ex: JIRA-123)"
                variant="outlined"
                density="compact"
                class="mb-3"
                :error="temErroCampo('id_externo')"
                :error-messages="mensagemCampo('id_externo')"
                :rules="[r => !r || /^[A-Z0-9_\-]{2,30}$/i.test(r) || 'Formato inválido']"
              />

              <v-alert
                v-if="Object.keys(errosApiCampos).length"
                type="warning"
                density="compact"
                variant="tonal"
                class="mb-3"
              >
                Corrija os campos destacados para continuar.
              </v-alert>

              <v-checkbox
                v-model="form.impacto_regulatorio"
                label="Impacto regulatório / compliance"
                density="compact"
                color="amber"
                hide-details
                class="mb-3"
              />

              <v-divider class="my-3" />
              <div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:8px;display:flex;align-items:center;gap:6px">
                <v-icon size="16" color="amber">mdi-source-pull</v-icon>
                Integração GitHub para publicação no Redmine
              </div>

              <v-switch
                v-model="githubForm.enabled"
                label="Importar issues do GitHub no passo 5"
                density="compact"
                hide-details
                color="amber"
                class="mb-2"
              />

              <div v-if="githubForm.enabled">
                <v-text-field
                  v-model="githubForm.repo"
                  label="Repositório (owner/repo)"
                  variant="outlined"
                  density="compact"
                  class="mb-2"
                  :rules="[r => !!r || 'Obrigatório quando integração GitHub está ativa']"
                />

                <v-row dense class="mb-1">
                  <v-col cols="4">
                    <v-select
                      v-model="githubForm.state"
                      :items="['open','closed','all']"
                      label="Estado"
                      variant="outlined"
                      density="compact"
                    />
                  </v-col>
                  <v-col cols="4">
                    <v-text-field
                      v-model.number="githubForm.limit"
                      type="number"
                      min="1"
                      max="100"
                      label="Limite"
                      variant="outlined"
                      density="compact"
                    />
                  </v-col>
                  <v-col cols="4">
                    <v-text-field
                      v-model="githubForm.labels"
                      label="Labels (csv)"
                      variant="outlined"
                      density="compact"
                    />
                  </v-col>
                </v-row>

                <v-row dense class="mb-1">
                  <v-col cols="4">
                    <v-text-field
                      v-model.number="githubForm.redmineProjectId"
                      type="number"
                      min="1"
                      label="Projeto Redmine (opcional)"
                      variant="outlined"
                      density="compact"
                    />
                  </v-col>
                  <v-col cols="4">
                    <v-text-field
                      v-model.number="githubForm.trackerId"
                      type="number"
                      min="1"
                      label="Tracker (opcional)"
                      variant="outlined"
                      density="compact"
                    />
                  </v-col>
                  <v-col cols="4">
                    <v-text-field
                      v-model.number="githubForm.priorityId"
                      type="number"
                      min="1"
                      label="Prioridade (opcional)"
                      variant="outlined"
                      density="compact"
                    />
                  </v-col>
                </v-row>

                <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:4px 0 8px">
                  <v-btn
                    size="small"
                    variant="outlined"
                    prepend-icon="mdi-refresh"
                    :loading="githubLoading"
                    @click="carregarIssuesGithub"
                  >Carregar issues</v-btn>
                  <span style="font-size:11px;color:var(--muted)">
                    {{ githubIssues.length }} issue(s) carregada(s) {{ githubSelecionadasCount > 0 ? `· ${githubSelecionadasCount} selecionada(s)` : '' }}
                  </span>
                </div>

                <div v-if="githubIssues.length" style="max-height:140px;overflow:auto;border:1px solid var(--border);border-radius:8px;padding:8px 10px;margin-bottom:8px;background:#121a27">
                  <v-checkbox
                    v-for="issue in githubIssues"
                    :key="issue.number"
                    v-model="githubForm.selectedIssueNumbers"
                    :value="issue.number"
                    density="compact"
                    hide-details
                    class="my-1"
                  >
                    <template #label>
                      <div style="display:flex;align-items:center;gap:6px;min-width:0">
                        <span style="font-size:11px;color:#94a3b8">#{{ issue.number }}</span>
                        <span style="font-size:12px;color:#e2e8f0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ issue.title }}</span>
                      </div>
                    </template>
                  </v-checkbox>
                </div>
              </div>

              <div class="draft-info" v-if="rascunhoSalvo">
                <v-icon size="14" color="grey">mdi-content-save</v-icon>
                Rascunho salvo automaticamente
              </div>
            </v-form>
          </v-card-text>
          <v-divider />
          <v-card-actions class="pa-4">
            <v-btn variant="text" size="small" @click="limparFormulario" :disabled="executando">
              Limpar
            </v-btn>
            <v-spacer />
            <v-btn
              color="amber"
              variant="flat"
              :loading="executando"
              :disabled="!formValido || executando"
              @click="executarPipeline"
              prepend-icon="mdi-play"
            >
              Executar Pipeline
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>

      <!-- Resultado / log -->
      <v-col cols="12" md="7">
        <v-card style="background:var(--card)!important;border:1px solid var(--border)!important">
          <v-card-title class="py-3 px-4" style="font-size:15px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            Resultado da Execução
            <v-chip v-if="resultado" :color="resultadoColor" size="x-small" class="ml-2">
              {{ resultadoStatus }}
            </v-chip>
            <v-spacer />
            <div v-if="resultado" style="display:flex;gap:4px;flex-wrap:wrap">
              <v-tooltip v-for="cat in logCategorias" :key="cat.value" :text="cat.hint" location="top">
                <template #activator="{ props }">
                  <v-chip
                    v-bind="props"
                    size="x-small"
                    :variant="filtroLog === cat.value ? 'flat' : 'outlined'"
                    :color="filtroLog === cat.value ? cat.color : undefined"
                    @click="filtroLog = filtroLog === cat.value ? '' : cat.value"
                  >{{ cat.label }}</v-chip>
                </template>
              </v-tooltip>
            </div>
          </v-card-title>
          <v-divider />

          <!-- Idle state -->
          <div v-if="!resultado && !executando" class="empty-state">
            <v-icon size="48" color="grey">mdi-pipe</v-icon>
            <div class="mt-2" style="color:var(--muted)">Preencha o formulário e execute o pipeline</div>
          </div>

          <!-- Log de execução -->
          <div v-else class="pa-4">

            <!-- Step logs -->
            <div v-for="step in stepsFiltrados" :key="step.key" class="step-log-item" v-show="step.log || step.status !== 'idle'">
              <div class="step-log-header" @click="step.expanded = !step.expanded" style="cursor:pointer">
                <v-icon size="14" :color="stepColor(step.status)" class="mr-1">{{ stepIcon(step.status) }}</v-icon>
                <span style="font-size:13px;font-weight:600">{{ step.label }}</span>
                <v-chip v-if="step.duration" size="x-small" variant="text" class="ml-1" style="color:var(--muted)">
                  {{ step.duration }}ms
                </v-chip>
                <v-spacer />
                <v-icon size="14" color="grey">{{ step.expanded ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
              </div>
              <div v-if="step.expanded && step.log" class="step-log-body">{{ step.log }}</div>
            </div>

            <!-- Resultado final -->
            <div v-if="resultado && resultado.requisito_id" class="result-box mt-4">
              <div class="result-row">
                <span class="result-key">Código</span>
                <code class="result-val">{{ resultado.requisito_id }}</code>
              </div>
              <div class="result-row" v-if="resultado.solicitacao_id">
                <span class="result-key">Solicitação</span>
                <code class="result-val">{{ resultado.solicitacao_id }}</code>
              </div>
              <div class="result-row" v-if="resultado.rfs_inferidas?.length">
                <span class="result-key">RFs detectadas</span>
                <div style="display:flex;gap:4px;flex-wrap:wrap">
                  <v-chip v-for="rf in resultado.rfs_inferidas" :key="rf" size="x-small" color="cyan">{{ rf }}</v-chip>
                </div>
              </div>
              <div class="result-row" v-if="resultado.redmine_url">
                <span class="result-key">Redmine</span>
                <a :href="resultado.redmine_url" target="_blank" class="result-link">{{ resultado.redmine_url }}</a>
              </div>
              <div class="result-row" v-if="resultado.github_imported_count">
                <span class="result-key">GitHub importadas</span>
                <code class="result-val">{{ resultado.github_imported_count }}</code>
              </div>
              <div class="result-row" v-if="resultado.redmine_published_count">
                <span class="result-key">Publicadas no Redmine</span>
                <code class="result-val">{{ resultado.redmine_published_count }}</code>
              </div>
              <div class="result-row" v-if="correlatioId">
                <span class="result-key">Correlation ID</span>
                <code class="result-val" style="font-size:11px">{{ correlatioId }}</code>
              </div>
            </div>

            <!-- Alertas de validação -->
            <div v-if="resultado?.alertas?.length" class="mt-3">
              <div class="result-row" v-for="alerta in resultado.alertas" :key="alerta">
                <v-icon size="14" color="warning" class="mr-1">mdi-alert</v-icon>
                <span style="font-size:12px;color:#fbbf24">{{ alerta }}</span>
              </div>
            </div>

          </div>
        </v-card>
      </v-col>
    </v-row>

    <v-card v-if="historicoExecucoes.length" class="mt-4 pa-4" style="background:var(--card)!important;border:1px solid var(--border)!important">
      <div class="d-flex align-center flex-wrap gap-2 mb-3">
        <strong>Analítico de execuções do pipeline</strong>
        <v-chip size="x-small" variant="tonal">{{ etapasHistoricoFiltradas.length }} etapas</v-chip>
        <v-spacer />
        <v-chip v-if="temFiltroHistoricoPipeline" size="x-small" color="amber" variant="tonal">Filtro ativo</v-chip>
      </div>
      <v-row dense class="mb-2">
        <v-col cols="12" sm="6" md="2">
          <v-select
            v-model="filtrosHistoricoPipeline.etapa"
            :items="etapaOptions"
            item-title="label"
            item-value="value"
            label="Etapa"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @update:model-value="sincronizarQueryHistoricoPipeline"
          />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-select
            v-model="filtrosHistoricoPipeline.status"
            :items="statusEtapaOptions"
            item-title="label"
            item-value="value"
            label="Status"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @update:model-value="sincronizarQueryHistoricoPipeline"
          />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-select
            v-model="filtrosHistoricoPipeline.categoria"
            :items="logCategorias"
            item-title="label"
            item-value="value"
            label="Categoria"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @update:model-value="sincronizarQueryHistoricoPipeline"
          />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-text-field
            v-model="filtrosHistoricoPipeline.data"
            label="Data"
            type="date"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @update:model-value="sincronizarQueryHistoricoPipeline"
          />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-text-field
            v-model="filtrosHistoricoPipeline.correlation_id"
            label="Correlation ID"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @update:model-value="sincronizarQueryHistoricoPipeline"
          />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-text-field
            v-model="filtrosHistoricoPipeline.duracao_min"
            label="Duração mín. (ms)"
            type="number"
            min="0"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @update:model-value="sincronizarQueryHistoricoPipeline"
          />
        </v-col>
      </v-row>
      <div class="d-flex justify-end mb-2">
        <v-btn variant="text" size="small" prepend-icon="mdi-filter-off" :disabled="!temFiltroHistoricoPipeline" @click="limparFiltrosHistoricoPipeline">
          Limpar filtros
        </v-btn>
      </div>
      <v-data-table
        :headers="historicoPipelineHeaders"
        :items="etapasHistoricoFiltradas"
        density="compact"
        :items-per-page="10"
      >
        <template #item.executadoEm="{ item }">
          <span style="font-size:11px">{{ formatarDataPipeline(item.executadoEm) }}</span>
        </template>
        <template #item.duration="{ item }">
          <span>{{ item.duration ?? '—' }} ms</span>
        </template>
        <template #item.status="{ item }">
          <v-chip size="x-small" :color="stepColor(item.status)" variant="tonal">{{ item.status }}</v-chip>
        </template>
        <template #item.correlationId="{ item }">
          <span
            v-if="item.correlationId"
            class="correlation-link"
            role="button"
            tabindex="0"
            @click="filtrarPipelinePorCorrelation(item.correlationId)"
          >{{ item.correlationId.slice(0, 12) }}…</span>
          <span v-else>—</span>
        </template>
      </v-data-table>
    </v-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from '../composables/useToast'
import { api } from '../services/api'
import {
  achatarHistoricoPipeline,
  carregarHistoricoPipeline,
  criarQueryFiltrosPipeline,
  criarRegistroExecucaoPipeline,
  filtrarEtapasPipeline,
  normalizarFiltrosPipeline,
  possuiFiltroAtivo,
  salvarHistoricoPipeline,
} from '../utils/filtrosPipeline'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const formRef = ref(null)
const formValido = ref(false)
const executando = ref(false)
const resultado = ref(null)
const rascunhoSalvo = ref(false)
const demoMode = ref(false)
const correlatioId = ref('')
const nivelFiltro = ref('micro')
const filtroLog = ref('')
const statusOrigemDemanda = ref('')
const snapshotAplicado = ref(false)
const errosApiCampos = ref({})
const refOrigem = ref(null)
const refTitulo = ref(null)
const refUrgencia = ref(null)
const refDescricao = ref(null)
const refArea = ref(null)
const refSistema = ref(null)
const refModulo = ref(null)
const refSolicitante = ref(null)
const refIdExterno = ref(null)
const githubLoading = ref(false)
const githubIssues = ref([])
const historicoExecucoes = ref([])
const filtrosHistoricoPipeline = reactive(normalizarFiltrosPipeline(route.query))

const etapaOptions = [
  { label: 'Normalização', value: 'normalizar' },
  { label: 'Solicitação', value: 'solicitacao' },
  { label: 'Validação', value: 'validar' },
  { label: 'Estruturação', value: 'estruturar' },
  { label: 'Publicar', value: 'publicar' },
]
const statusEtapaOptions = [
  { label: 'OK', value: 'ok' },
  { label: 'Aviso', value: 'warn' },
  { label: 'Erro', value: 'error' },
  { label: 'Executando', value: 'running' },
]
const historicoPipelineHeaders = [
  { title: 'Data', key: 'executadoEm', width: '130px' },
  { title: 'Etapa', key: 'label' },
  { title: 'Status', key: 'status', width: '90px' },
  { title: 'Duração', key: 'duration', width: '90px' },
  { title: 'Responsável', key: 'solicitante', width: '120px' },
  { title: 'Correlation ID', key: 'correlationId', width: '130px' },
  { title: 'Log', key: 'log' },
]

const etapasHistoricoFiltradas = computed(() => filtrarEtapasPipeline(
  achatarHistoricoPipeline(historicoExecucoes.value),
  filtrosHistoricoPipeline,
))
const temFiltroHistoricoPipeline = computed(() => possuiFiltroAtivo(filtrosHistoricoPipeline))

watch(
  () => route.query,
  (query) => Object.assign(filtrosHistoricoPipeline, normalizarFiltrosPipeline(query)),
)

const githubForm = reactive({
  enabled: false,
  repo: '',
  state: 'open',
  limit: 10,
  labels: '',
  redmineProjectId: null,
  trackerId: null,
  priorityId: null,
  selectedIssueNumbers: [],
})

const githubLabelsArray = computed(() => {
  return String(githubForm.labels || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
})

const githubSelecionadasCount = computed(() => githubForm.selectedIssueNumbers.length)

const logCategorias = [
  { value: 'erro',      label: 'Erro',       color: 'red',    hint: 'Steps com falha ou status de erro' },
  { value: 'aviso',     label: 'Aviso',      color: 'orange', hint: 'Steps com atenção ou warnings' },
  { value: 'pipeline',  label: 'Pipeline',   color: 'blue',   hint: 'Steps de publicação e integração' },
  { value: 'ok',        label: 'Concluídos', color: 'green',  hint: 'Steps finalizados com sucesso' },
]

function categoriaStep(step) {
  if (step.status === 'error') return 'erro'
  if (step.status === 'warn') return 'aviso'
  if (step.key === 'publicar') return 'pipeline'
  return 'ok'
}

const stepsFiltrados = computed(() => {
  if (nivelFiltro.value === 'micro' || !filtroLog.value) return steps
  return steps.filter(s => categoriaStep(s) === filtroLog.value)
})

const DRAFT_KEY = 'reqsys_pipeline_draft'
const PREFILL_KEY = 'reqsys_pipeline_prefill'
const LEGEND_KEY = 'reqsys_pipeline_legend_status'

const origens = ['email', 'reuniao', 'sistema_externo', 'cliente', 'regulatorio']
const urgencias = ['critica', 'alta', 'media', 'baixa']

const form = reactive({
  origem: 'email',
  titulo: '',
  urgencia: 'media',
  descricao: '',
  area: '',
  sistema: '',
  modulo: '',
  solicitante: '',
  id_externo: '',
  impacto_regulatorio: false,
})

const steps = reactive([
  { key: 'normalizar',   label: '1. Normalização',      status: 'idle', log: '', duration: null, expanded: true },
  { key: 'solicitacao',  label: '2. Solicitação',        status: 'idle', log: '', duration: null, expanded: true },
  { key: 'validar',      label: '3. Validação Semântica', status: 'idle', log: '', duration: null, expanded: true },
  { key: 'estruturar',   label: '4. Estruturação',        status: 'idle', log: '', duration: null, expanded: true },
  { key: 'publicar',     label: '5. Publicar Redmine',   status: 'idle', log: '', duration: null, expanded: true },
])

const currentStep = ref(0)
const resultadoStatus = ref('')
const resultadoColor = ref('success')

// ---- Rascunho automático ----
watch([form, githubForm], () => {
  localStorage.setItem(DRAFT_KEY, JSON.stringify({
    ...form,
    githubForm: { ...githubForm },
  }))
  rascunhoSalvo.value = true
}, { deep: true })

onMounted(() => {
  historicoExecucoes.value = carregarHistoricoPipeline()

  const saved = localStorage.getItem(DRAFT_KEY)
  if (saved) {
    try {
      const data = JSON.parse(saved)
      Object.assign(form, {
        origem: data.origem || 'email',
        titulo: data.titulo || '',
        urgencia: data.urgencia || 'media',
        descricao: data.descricao || '',
        area: data.area || '',
        sistema: data.sistema || '',
        modulo: data.modulo || '',
        solicitante: data.solicitante || '',
        id_externo: data.id_externo || '',
        impacto_regulatorio: Boolean(data.impacto_regulatorio),
      })
      if (data.githubForm && typeof data.githubForm === 'object') {
        Object.assign(githubForm, data.githubForm)
      }
      rascunhoSalvo.value = true
    } catch {}
  }

  const prefill = sessionStorage.getItem(PREFILL_KEY)
  if (prefill) {
    try {
      const data = JSON.parse(prefill)
      Object.assign(form, {
        origem: data.origem || 'sistema_externo',
        titulo: data.titulo || '',
        urgencia: data.urgencia || 'media',
        descricao: data.descricao || '',
        area: data.area || '',
        sistema: data.sistema || '',
        modulo: data.modulo || '',
        solicitante: data.solicitante || '',
        id_externo: data.id_externo || '',
        impacto_regulatorio: Boolean(data.impacto_regulatorio),
      })
      aplicarStatusInicialDemanda(data.status_demanda)
      rascunhoSalvo.value = true
      toast.success(`Demanda carregada no Pipeline (status: ${data.status_demanda || 'recebido'})`)
    } catch {}
    sessionStorage.removeItem(PREFILL_KEY)
    return
  }

  const legendaSalva = sessionStorage.getItem(LEGEND_KEY)
  if (legendaSalva) {
    aplicarStatusInicialDemanda(legendaSalva)
    toast.info(`Preview restaurado: ${statusOrigemLabel(legendaSalva)}`)
  }
})

function limparFormulario() {
  Object.assign(form, {
    origem: 'email', titulo: '', urgencia: 'media', descricao: '',
    area: '', sistema: '', modulo: '', solicitante: '', id_externo: '', impacto_regulatorio: false
  })
  localStorage.removeItem(DRAFT_KEY)
  rascunhoSalvo.value = false
  Object.assign(githubForm, {
    enabled: false,
    repo: '',
    state: 'open',
    limit: 10,
    labels: '',
    redmineProjectId: null,
    trackerId: null,
    priorityId: null,
    selectedIssueNumbers: [],
  })
  githubIssues.value = []
  resultado.value = null
  correlatioId.value = ''
  statusOrigemDemanda.value = ''
  snapshotAplicado.value = false
  sessionStorage.removeItem(LEGEND_KEY)
  resetSteps()
}

function resetSteps() {
  steps.forEach(s => { s.status = 'idle'; s.log = ''; s.duration = null })
  currentStep.value = 0
}

function aplicarStatusInicialDemanda(statusDemanda) {
  const status = String(statusDemanda || '').toLowerCase()
  const statusValidos = ['idle', 'running', 'ok', 'warn', 'error']
  statusOrigemDemanda.value = status || ''
  snapshotAplicado.value = false

  // Compatibilidade caso o status já venha no padrão visual interno do pipeline.
  if (statusValidos.includes(status)) {
    resetSteps()
    steps.forEach((s, idx) => {
      s.status = status
      s.log = `Status inicial importado da demanda: ${status}`
      currentStep.value = idx
    })
    snapshotAplicado.value = true
    sessionStorage.setItem(LEGEND_KEY, status)
    return
  }

  const mapaDemanda = {
    recebido: ['ok', 'idle', 'idle', 'idle', 'idle'],
    em_analise: ['ok', 'ok', 'running', 'idle', 'idle'],
    aprovado: ['ok', 'ok', 'ok', 'ok', 'running'],
    publicado: ['ok', 'ok', 'ok', 'ok', 'ok'],
    rejeitado: ['ok', 'ok', 'error', 'idle', 'idle'],
    concluido: ['ok', 'ok', 'ok', 'ok', 'ok'],
  }

  const statusPorStep = mapaDemanda[status]
  if (!statusPorStep) {
    statusOrigemDemanda.value = ''
    snapshotAplicado.value = false
    sessionStorage.removeItem(LEGEND_KEY)
    return
  }

  resetSteps()
  steps.forEach((s, idx) => {
    s.status = statusPorStep[idx]
    s.log = `Snapshot inicial da demanda (${status})`
    if (statusPorStep[idx] === 'running' || statusPorStep[idx] === 'error') {
      currentStep.value = idx
    }
  })
  snapshotAplicado.value = true
  sessionStorage.setItem(LEGEND_KEY, status)
}

function statusOrigemLabel(status) {
  return {
    recebido: 'Recebido',
    em_analise: 'Em análise',
    aprovado: 'Aprovado',
    rejeitado: 'Rejeitado',
    publicado: 'Publicado',
    concluido: 'Concluído',
    idle: 'Neutro',
    running: 'Em execução',
    ok: 'Concluído',
    warn: 'Atenção',
    error: 'Erro',
  }[status] || status
}

function statusOrigemColor(status) {
  return {
    recebido: 'blue',
    em_analise: 'orange',
    aprovado: 'green',
    rejeitado: 'red',
    publicado: 'teal',
    concluido: 'teal',
    idle: 'grey',
    running: 'amber',
    ok: 'green',
    warn: 'orange',
    error: 'red',
  }[status] || 'grey'
}

function limparContextoOrigem() {
  statusOrigemDemanda.value = ''
  snapshotAplicado.value = false
  sessionStorage.removeItem(LEGEND_KEY)
  resetSteps()
  toast.info('Contexto importado removido. Steps resetados.')
}

function isLegendaAtiva(status) {
  return snapshotAplicado.value && statusOrigemDemanda.value === status
}

function toggleLegendaStatus(status) {
  if (isLegendaAtiva(status)) {
    limparContextoOrigem()
    return
  }
  aplicarStatusInicialDemanda(status)
  toast.info(`Preview aplicado: ${statusOrigemLabel(status)}`)
}

async function copiarCorrelation() {
  try {
    await navigator.clipboard.writeText(correlatioId.value)
    toast.success('Correlation ID copiado!')
  } catch {
    toast.info(correlatioId.value)
  }
}

// ---- Pipeline ----
async function executarPipeline() {
  const { valid } = await formRef.value.validate()
  if (!valid) return

  limparErrosApiCampos()
  executando.value = true
  resultado.value = null
  correlatioId.value = `corr-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  resetSteps()

  try {
    if (demoMode.value) {
      await executarDemo()
    } else {
      await executarReal()
    }
    resultadoStatus.value = 'CONCLUÍDO'
    resultadoColor.value = 'success'
    toast.success('Pipeline executado com sucesso!')
    localStorage.removeItem(DRAFT_KEY)
    rascunhoSalvo.value = false
  } catch (err) {
    mapearErrosApiParaCampos(err)
    await scrollParaPrimeiroCampoComErro()
    resultadoStatus.value = 'ERRO'
    resultadoColor.value = 'error'
    const mensagem = formatarErroApi(err)
    registrarErroNoStepAtual(mensagem)
    toast.error(mensagem)
  } finally {
    registrarHistoricoExecucao()
    executando.value = false
  }
}

function registrarHistoricoExecucao() {
  if (!correlatioId.value) return
  const registro = criarRegistroExecucaoPipeline({
    correlationId: correlatioId.value,
    steps: steps.map((step) => ({ ...step })),
    solicitante: form.solicitante,
    modoDemo: demoMode.value,
    statusGeral: resultadoStatus.value === 'CONCLUÍDO' ? 'CONCLUIDO' : 'ERRO',
  })
  historicoExecucoes.value = [registro, ...historicoExecucoes.value].slice(0, 30)
  salvarHistoricoPipeline(historicoExecucoes.value)
}

function sincronizarQueryHistoricoPipeline() {
  router.replace({ path: route.path, query: criarQueryFiltrosPipeline(filtrosHistoricoPipeline) })
}

function limparFiltrosHistoricoPipeline() {
  Object.assign(filtrosHistoricoPipeline, {
    etapa: '', status: '', categoria: '', correlation_id: '', data: '', busca: '', duracao_min: 0,
  })
  sincronizarQueryHistoricoPipeline()
}

function filtrarPipelinePorCorrelation(correlationId) {
  filtrosHistoricoPipeline.correlation_id = correlationId
  sincronizarQueryHistoricoPipeline()
}

function formatarDataPipeline(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

async function executarReal() {
  const headers = { 'X-Correlation-ID': correlatioId.value }

  // Step 1 — normalizar (client-side)
  setStep(0, 'running')
  await delay(200)
  const normalizado = {
    titulo: form.titulo.trim(),
    descricao: form.descricao.trim(),
    urgencia: form.urgencia,
    origem: form.origem,
    area: form.area?.trim() || 'Geral',
    sistema: form.sistema?.trim() || 'ReqSys',
    modulo: form.modulo || undefined,
    solicitante: form.solicitante?.trim() || 'Usuário interno',
    id_externo: form.id_externo || undefined,
    impacto_regulatorio: form.impacto_regulatorio,
  }
  setStep(0, 'ok', `Campos normalizados: ${Object.keys(normalizado).filter(k => normalizado[k]).length} preenchidos`)

  // Step 2 — criar solicitação
  setStep(1, 'running')
  const t1 = Date.now()
  const solResp = await api.post('/v1/solicitacoes', normalizado, { headers })
  setStep(1, 'ok', `Solicitação criada: ${solResp.data?.data?.codigo || '—'}`, Date.now() - t1)
  const solId = solResp.data?.data?.codigo || solResp.data?.data?.id

  // Step 3 — validar semântica
  setStep(2, 'running')
  const t2 = Date.now()
  const valResp = await api.post('/v1/requisitos/validar', normalizado, { headers })
  const valData = valResp.data?.data
  const valAprovado = Boolean(valData?.aprovado_para_triagem)
  const valStatus = valAprovado ? 'ok' : 'warn'
  const alertas = valData?.alertas || []
  setStep(2, valStatus,
    `Aprovado para triagem: ${valAprovado ? 'Sim' : 'Não'}${alertas.length ? ' | ' + alertas.join('; ') : ''}`,
    Date.now() - t2
  )

  // Step 4 — estruturar (precisa de um requisito_id; usa o retorno da solicitação ou 1 como fallback)
  setStep(3, 'running')
  const t3 = Date.now()
  const reqId = solResp.data?.data?.id || 1
  const estResp = await api.post(`/v1/requisitos/estruturar/${reqId}`, normalizado, { headers })
  const estData = estResp.data?.data
  setStep(3, 'ok',
    `RFs: ${estData?.requisitos_funcionais?.length || 0} | Critérios: ${estData?.criterios_aceite?.length || 0}`,
    Date.now() - t3
  )

  // Step 5 — publicar redmine
  setStep(4, 'running')
  const t4 = Date.now()
  if (githubForm.enabled && githubForm.repo && githubIssues.value.length === 0) {
    await carregarIssuesGithub()
  }
  const publicarPayload = {
    use_github_import: Boolean(githubForm.enabled && githubForm.repo),
    github_repo: githubForm.repo || null,
    github_state: githubForm.state,
    github_limit: githubForm.limit,
    github_labels: githubLabelsArray.value,
    issue_numbers: githubForm.selectedIssueNumbers,
    redmine_project_id: githubForm.redmineProjectId || null,
    tracker_id: githubForm.trackerId || null,
    priority_id: githubForm.priorityId || null,
  }
  const pubResp = await api.post(`/v1/backlog/publicar-redmine/${reqId}`, publicarPayload, { headers })
  const pubData = pubResp.data?.data
  setStep(4, 'ok',
    `Story: ${pubData?.issue_principal_id || '—'} | Subtarefas: ${pubData?.subtarefas?.length || 0}`,
    Date.now() - t4
  )

  resultado.value = {
    requisito_id: estData?.requisito_id || `REQ-${Date.now()}`,
    solicitacao_id: solId,
    rfs_inferidas: estData?.requisitos_funcionais || [],
    redmine_url: pubData?.issue_principal_id ? `${REDMINE_BASE_URL}/issues/${pubData.issue_principal_id}` : undefined,
    github_imported_count: pubData?.github_imported_count || 0,
    redmine_published_count: pubData?.redmine_published_count || 0,
    alertas,
  }

  if (Array.isArray(pubData?.warnings) && pubData.warnings.length) {
    toast.info(pubData.warnings.join(' | '))
  }
}

async function carregarIssuesGithub() {
  if (!githubForm.repo) {
    toast.error('Informe o repositório no formato owner/repo.')
    return
  }
  githubLoading.value = true
  try {
    const resp = await api.post('/v1/integracoes/github/issues', {
      repo: githubForm.repo,
      state: githubForm.state,
      limit: githubForm.limit,
      labels: githubLabelsArray.value,
    })
    const issues = resp.data?.data?.issues || []
    githubIssues.value = issues
    const existentes = new Set(issues.map((i) => i.number))
    githubForm.selectedIssueNumbers = githubForm.selectedIssueNumbers.filter((n) => existentes.has(n))
    toast.success(`${issues.length} issue(s) carregada(s) do GitHub.`)
  } catch (err) {
    const msg = formatarErroApi(err)
    toast.error(msg)
  } finally {
    githubLoading.value = false
  }
}

async function executarDemo() {
  const demoPipeline = [
    { log: 'Campos normalizados · urgência=media · origem=email · 6 campos preenchidos', dur: 120 },
    { log: 'Solicitação criada: SOL-1746000001 · normalização aplicada', dur: 380 },
    { log: 'Semântica válida · nenhum termo ambíguo · 2 RFs inferidas (RF-AUTH, RF-RELAT)', dur: 510, status: 'ok' },
    { log: 'Estruturado · 2 RFs · 3 RNFs · 4 regras de negócio · 5 critérios de aceite', dur: 720 },
    { log: 'Story #42 criado · 4 subtarefas (Frontend, Backend, Dados, QA) · redmine-deveri.local/issues/42', dur: 640 },
  ]

  for (let i = 0; i < demoPipeline.length; i++) {
    setStep(i, 'running')
    await delay(demoPipeline[i].dur)
    setStep(i, demoPipeline[i].status || 'ok', demoPipeline[i].log, demoPipeline[i].dur)
  }

  resultado.value = {
    requisito_id: 'REQ-DEMO-001',
    solicitacao_id: 'SOL-1746000001',
    rfs_inferidas: ['RF-AUTH', 'RF-RELAT'],
    redmine_url: `${REDMINE_BASE_URL}/issues/42`,
    alertas: [],
  }
}

function setStep(idx, status, log = '', duration = null) {
  steps[idx].status = status
  if (log) steps[idx].log = log
  if (duration !== null) steps[idx].duration = duration
  currentStep.value = idx
}

function registrarErroNoStepAtual(mensagem) {
  const idx = steps.findIndex((s) => s.status === 'running')
  const target = idx >= 0 ? idx : currentStep.value
  if (target >= 0 && target < steps.length) {
    setStep(target, 'error', mensagem)
  }
}

function limparErrosApiCampos() {
  errosApiCampos.value = {}
}

function mapearErrosApiParaCampos(err) {
  const detail = err?.response?.data?.detail
  if (!Array.isArray(detail)) return

  const prox = {}
  for (const item of detail) {
    const loc = Array.isArray(item?.loc) ? item.loc : []
    const campo = loc[loc.length - 1]
    if (!campo || typeof campo !== 'string') continue
    const msg = item?.msg || 'valor inválido'
    if (!prox[campo]) prox[campo] = []
    prox[campo].push(msg)
  }
  errosApiCampos.value = prox
}

function temErroCampo(campo) {
  return Array.isArray(errosApiCampos.value[campo]) && errosApiCampos.value[campo].length > 0
}

function mensagemCampo(campo) {
  return errosApiCampos.value[campo] || []
}

const REDMINE_BASE_URL = (import.meta.env.VITE_REDMINE_URL || 'https://redmine-deveri.local').replace(/\/$/, '')

const labelsCampos = {
  origem: 'Origem',
  titulo: 'Título',
  urgencia: 'Urgência',
  descricao: 'Descrição',
  area: 'Área',
  sistema: 'Sistema',
  modulo: 'Módulo',
  solicitante: 'Solicitante',
  id_externo: 'ID Externo',
}

async function scrollParaCampo(campo) {
  const refs = {
    origem: refOrigem,
    titulo: refTitulo,
    urgencia: refUrgencia,
    descricao: refDescricao,
    area: refArea,
    sistema: refSistema,
    modulo: refModulo,
    solicitante: refSolicitante,
    id_externo: refIdExterno,
  }
  await nextTick()
  const raw = refs[campo]?.value
  const el = raw?.$el || raw
  if (!el) return
  const target = el.querySelector?.('input,textarea,select') || el
  target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  setTimeout(() => target.focus?.(), 300)
}

async function scrollParaPrimeiroCampoComErro() {
  const ordem = ['origem', 'titulo', 'urgencia', 'descricao', 'area', 'sistema', 'modulo', 'solicitante', 'id_externo']
  const refs = {
    origem: refOrigem,
    titulo: refTitulo,
    urgencia: refUrgencia,
    descricao: refDescricao,
    area: refArea,
    sistema: refSistema,
    modulo: refModulo,
    solicitante: refSolicitante,
    id_externo: refIdExterno,
  }

  const campo = ordem.find((c) => temErroCampo(c))
  if (!campo) return

  await nextTick()
  const raw = refs[campo]?.value
  const el = raw?.$el || raw
  if (!el) return

  el.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  const input = el.querySelector?.('input, textarea, [role="combobox"]')
  input?.focus?.()
}

function formatarErroApi(err) {
  const status = err?.response?.status
  const detail = err?.response?.data?.detail

  if (status === 422 && Array.isArray(detail) && detail.length) {
    const campos = detail.map((d) => {
      const loc = Array.isArray(d?.loc) ? d.loc.join('.') : 'campo'
      return `${loc}: ${d?.msg || 'valor inválido'}`
    })
    return `Validação falhou (422): ${campos.join(' | ')}`
  }

  if (typeof detail === 'string' && detail.trim()) {
    return `Erro ${status || ''}: ${detail}`.trim()
  }

  if (err?.message) {
    return err.message
  }

  return 'Erro ao executar pipeline'
}

function delay(ms) {
  return new Promise(res => setTimeout(res, ms))
}

function stepIcon(status) {
  return { ok: 'mdi-check-circle', error: 'mdi-close-circle', warn: 'mdi-alert-circle', running: 'mdi-loading', idle: 'mdi-circle-outline' }[status] || 'mdi-circle-outline'
}

function stepColor(status) {
  return { ok: 'success', error: 'error', warn: 'warning', running: 'amber', idle: 'grey' }[status] || 'grey'
}

function toastIcon(type) {
  return { success: 'mdi-check', error: 'mdi-close', warning: 'mdi-alert', info: 'mdi-information' }[type] || 'mdi-information'
}
</script>

<style scoped>
.steps-bar {
  display: flex;
  align-items: center;
  gap: 0;
  overflow-x: auto;
}
.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  flex: 1;
  min-width: 100px;
}
.step-badge {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}
.step-label {
  font-size: 11px;
  color: var(--muted);
  margin-top: 6px;
  text-align: center;
}
.step-connector {
  position: absolute;
  top: 16px;
  right: -50%;
  width: 100%;
  height: 2px;
  background: var(--border);
  z-index: 0;
}
.step-done .step-badge   { background: #166534; }
.step-done .step-label   { color: #4ade80; }
.step-error .step-badge  { background: #7f1d1d; }
.step-error .step-label  { color: #f87171; }
.step-warn .step-badge   { background: #78350f; }
.step-warn .step-label   { color: #fbbf24; }
.step-running .step-badge { background: #451a03; border: 1px solid #f59e0b; }
.step-active .step-badge  { border: 2px solid var(--accent); }

.step-log-item { border-left: 2px solid var(--border); padding: 6px 10px; margin-bottom: 4px; border-radius: 0 6px 6px 0; }
.step-log-header { display: flex; align-items: center; gap: 4px; }
.step-log-body { font-size: 11px; color: var(--muted); margin-top: 4px; font-family: 'JetBrains Mono', monospace; white-space: pre-wrap; }

.result-box { background: #0a1628; border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
.result-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.result-key { font-size: 11px; color: var(--muted); min-width: 90px; }
.result-val { font-size: 12px; color: var(--accent); background: #1a2640; padding: 2px 6px; border-radius: 4px; }
.result-link { font-size: 12px; color: #60a5fa; text-decoration: underline; }

.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 300px; }

.demo-badge { background: #7c3aed; color: white; font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 700; letter-spacing: 1px; }
.draft-info { font-size: 11px; color: var(--muted); display: flex; align-items: center; gap: 4px; }

/* Toasts */
.toast-container { position: fixed; top: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 8px; }
.toast-item { padding: 10px 16px; border-radius: 8px; font-size: 13px; cursor: pointer; display: flex; align-items: center; min-width: 220px; max-width: 360px; box-shadow: 0 4px 16px #0008; }
.toast-success  { background: #14532d; border: 1px solid #4ade80; color: #bbf7d0; }
.toast-error    { background: #7f1d1d; border: 1px solid #f87171; color: #fecaca; }
.toast-warning  { background: #451a03; border: 1px solid #fbbf24; color: #fef3c7; }
.toast-info     { background: #1e3a5f; border: 1px solid #60a5fa; color: #bfdbfe; }
.toast-enter-active, .toast-leave-active { transition: all .25s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(40px); }
.correlation-link { color: var(--accent); cursor: pointer; text-decoration: underline dotted; font-size: 11px; }
</style>
