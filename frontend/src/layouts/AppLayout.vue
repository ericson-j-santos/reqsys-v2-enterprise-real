<template>
  <v-layout class="req-layout">
    <!-- Mobile app bar -->
    <v-app-bar v-if="mobile" flat class="req-appbar" elevation="0" height="56">
      <v-app-bar-nav-icon color="white" aria-label="Abrir menu de navegação" @click="drawer = !drawer" />
      <span class="brand-sm ml-1"><span class="brand-dot brand-dot--sm">R</span> ReqSys</span>
      <span class="figma-pill figma-pill--compact ml-2">{{ environmentLabelShort }}</span>
      <v-spacer />
      <v-chip size="x-small" color="amber" variant="tonal" class="mr-2 req-role-chip">
        {{ auth.usuario?.papel || 'user' }}
      </v-chip>
    </v-app-bar>

    <!-- Navigation drawer -->
    <v-navigation-drawer
      v-model="drawer"
      :permanent="!mobile"
      :temporary="mobile"
      width="280"
      class="req-drawer"
    >
      <div class="pa-5 pb-3 req-brand-block">
        <div class="brand"><span class="brand-dot">R</span> ReqSys Enterprise</div>
        <div class="muted mt-1 version-line" data-testid="app-version-label">{{ versionLabel }}</div>
        <v-chip
          v-if="hasVersionDrift"
          size="x-small"
          color="warning"
          variant="tonal"
          class="mt-1"
          prepend-icon="mdi-alert-outline"
          data-testid="app-version-drift-chip"
        >
          Versões divergentes
        </v-chip>
        <span class="figma-pill figma-pill--compact mt-2 d-inline-block">Ambiente: {{ ambienteDrawerLabel }}</span>
      </div>
      <v-divider />

      <!-- Abas por tema de negócio -->
      <div class="nav-temas" aria-label="Temas de navegação">
        <v-tabs
          v-model="temaAtivo"
          density="compact"
          color="primary"
          class="nav-temas-tabs"
          show-arrows
        >
          <v-tab
            v-for="tema in NAV_TEMAS"
            :key="tema.id"
            :value="tema.id"
            :data-testid="`nav-tema-${tema.id}`"
            class="nav-tema-tab"
          >
            <span class="nav-tema-tab-inner">
              <v-icon :icon="tema.icon" size="16" />
              <span class="nav-tema-label">{{ tema.title }}</span>
              <span
                v-if="badgeTema(tema.id).count > 0"
                class="nav-tema-badge"
                :class="`nav-tema-badge--${badgeTema(tema.id).level}`"
                :data-testid="`nav-badge-${tema.id}`"
                :title="`${badgeTema(tema.id).count} pendência(s)`"
              >
                {{ badgeLabel(badgeTema(tema.id).count) }}
              </span>
            </span>
          </v-tab>
        </v-tabs>
        <p class="nav-tema-topic muted">{{ temaAtual.topic }}</p>
      </div>

      <!-- Sub-abas do tema Requisitos (Entrada / Pipeline / Publicação) -->
      <div
        v-if="temaTemSubgrupos(temaAtivo)"
        class="nav-subgrupos"
        aria-label="Subtemas de Requisitos"
      >
        <v-tabs
          v-model="subgrupoAtivo"
          density="compact"
          color="secondary"
          class="nav-subgrupos-tabs"
        >
          <v-tab
            v-for="sub in temaAtual.subgroups"
            :key="sub.id"
            :value="sub.id"
            :data-testid="`nav-subgrupo-${sub.id}`"
            class="nav-subgrupo-tab"
          >
            {{ sub.title }}
          </v-tab>
        </v-tabs>
        <p v-if="subgrupoAtualInfo" class="nav-subgrupo-topic muted">{{ subgrupoAtualInfo.topic }}</p>
      </div>

      <!-- Sub-rotas do tema (ou do subgrupo ativo) -->
      <v-list density="compact" nav class="pt-1 req-nav-list" aria-label="Navegação do tema">
        <v-tooltip
          v-for="item in itensVisiveis"
          :key="item.to"
          :text="item.tip"
          location="right"
        >
          <template #activator="{ props }">
            <v-list-item
              v-bind="props"
              :to="item.to"
              :prepend-icon="item.icon"
              :title="item.title"
              class="nav-item"
              :data-testid="`nav-item-${navItemTestId(item.to)}`"
              @click="mobile && (drawer = false)"
            />
          </template>
        </v-tooltip>
      </v-list>

      <template #append>
        <v-divider />
        <div v-if="auth.usuario" class="user-info">
          <v-avatar size="30" color="amber" aria-hidden="true">
            <span class="user-initials">{{ initials(auth.usuario) }}</span>
          </v-avatar>
          <div class="overflow-hidden">
            <div class="user-name">{{ auth.usuario.nome || auth.usuario.email }}</div>
            <div class="muted user-role">{{ auth.usuario.papel }}</div>
          </div>
        </div>
        <v-list density="compact" class="pb-2">
          <v-list-item
            prepend-icon="mdi-logout"
            title="Sair"
            class="nav-item logout-item"
            @click="sair"
          />
        </v-list>
      </template>
    </v-navigation-drawer>

    <v-main class="req-main">
      <div class="req-content-shell">
        <router-view />
      </div>
    </v-main>
  </v-layout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import { useAuthStore } from '../stores/auth'
import { api } from '../services/api'
import { carregarDadosPendenciasNav } from '../composables/navPendencias'
import {
  lerSubgrupoRequisitosPersistido,
  lerTemaPersistido,
  salvarSubgrupoRequisitosPersistido,
  salvarTemaPersistido,
} from '../composables/navTemaPersist'
import {
  NAV_TEMAS,
  itensDoSubgrupo,
  subgrupoAtual,
  subgrupoIdPorRota,
  temaIdPorRota,
  temaPorId,
  temaTemSubgrupos,
} from '../constants/navCatalog'
import { useAppVersion } from '../composables/useAppVersion'

const { mobile } = useDisplay()
const { versionLabel, hasVersionDrift } = useAppVersion()
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const drawer = ref(!mobile.value)
const environment = ref(import.meta.env.VITE_APP_ENVIRONMENT || '')
const pendenciasPorTema = ref({})
const navegacaoInicializada = ref(false)

const temaAtivo = ref(temaIdPorRota(route.path))
const subgrupoAtivo = ref(subgrupoIdPorRota(route.path) || lerSubgrupoRequisitosPersistido() || 'entrada')

const environmentLabelShort = computed(() => {
  const value = (environment.value || 'dev').toLowerCase()
  if (['prod', 'producao', 'production'].includes(value)) return 'prod'
  if (['staging', 'homolog', 'homologacao', 'hml'].includes(value)) return 'stg'
  return 'dev'
})

const ambienteDrawerLabel = computed(() => {
  return (environment.value || 'desenvolvimento').replace(/_/g, ' ')
})

const temaAtual = computed(() => temaPorId(temaAtivo.value))

const subgrupoAtualInfo = computed(() =>
  temaTemSubgrupos(temaAtivo.value) ? subgrupoAtual(temaAtivo.value, subgrupoAtivo.value) : null,
)

const itensVisiveis = computed(() => {
  if (temaTemSubgrupos(temaAtivo.value)) {
    return itensDoSubgrupo(temaAtivo.value, subgrupoAtivo.value)
  }
  return temaAtual.value.items
})

watch(mobile, (isMobile) => {
  drawer.value = !isMobile
})

watch(temaAtivo, (id) => {
  salvarTemaPersistido(id)
  if (temaTemSubgrupos(id) && !subgrupoAtivo.value) {
    subgrupoAtivo.value = lerSubgrupoRequisitosPersistido() || temaAtual.value.subgroups[0].id
  }
})

watch(subgrupoAtivo, (id) => {
  if (temaTemSubgrupos(temaAtivo.value)) {
    salvarSubgrupoRequisitosPersistido(id)
  }
})

watch(
  () => route.path,
  (path) => {
    temaAtivo.value = temaIdPorRota(path)
    if (temaTemSubgrupos(temaAtivo.value)) {
      subgrupoAtivo.value = subgrupoIdPorRota(path) || subgrupoAtivo.value
    }
  },
)

onMounted(async () => {
  if (!navegacaoInicializada.value) {
    const persistido = lerTemaPersistido()
    const rotaTema = temaIdPorRota(route.path)
    if (route.path === '/' && persistido && persistido !== rotaTema) {
      temaAtivo.value = persistido
      if (temaTemSubgrupos(persistido)) {
        subgrupoAtivo.value = lerSubgrupoRequisitosPersistido() || 'entrada'
      }
    }
    navegacaoInicializada.value = true
  }

  try {
    const { data } = await api.get('/v1/auth/config')
    if (data?.data?.environment) environment.value = data.data.environment
  } catch {
    /* fallback build */
  }

  try {
    pendenciasPorTema.value = await carregarDadosPendenciasNav(api)
  } catch {
    pendenciasPorTema.value = {}
  }
})

function badgeTema(temaId) {
  return pendenciasPorTema.value[temaId] ?? { count: 0, level: null }
}

function badgeLabel(count) {
  return count > 99 ? '99+' : String(count)
}

function navItemTestId(path) {
  return path.replace(/\//g, '').replace(/^$/, 'dashboard')
}

function initials(u) {
  return (u.nome || u.email || '?')[0].toUpperCase()
}

function sair() {
  auth.sair()
  router.push('/login')
}
</script>

<style scoped>
.req-appbar {
  background: rgba(2, 6, 23, 0.92) !important;
}
.brand-sm {
  color: var(--text);
  font-weight: 800;
  font-size: 16px;
  letter-spacing: -0.01em;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.brand-dot--sm {
  width: 22px;
  height: 22px;
  font-size: 11px;
}
.figma-pill--compact {
  padding: 4px 10px;
  font-size: 11px;
}
.req-brand-block {
  min-width: 0;
}
.version-line {
  font-size: 11px;
  letter-spacing: 0.02em;
}
.nav-temas {
  padding: 8px 8px 0;
}
.nav-temas-tabs :deep(.v-slide-group__content) {
  gap: 2px;
}
.nav-tema-tab {
  min-width: auto !important;
  padding-inline: 6px !important;
  font-size: 11px;
  font-weight: 700;
  text-transform: none;
  letter-spacing: 0;
}
.nav-tema-tab-inner {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
}
.nav-tema-label {
  max-width: 58px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nav-tema-badge {
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  font-size: 9px;
  font-weight: 800;
  line-height: 16px;
  text-align: center;
  color: #111;
}
.nav-tema-badge--amarelo {
  background: var(--amber);
}
.nav-tema-badge--vermelho {
  background: var(--red);
  color: #fff;
}
.nav-tema-topic {
  margin: 6px 12px 4px;
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.nav-subgrupos {
  padding: 4px 8px 0;
  border-top: 1px solid var(--line);
  margin-top: 4px;
}
.nav-subgrupos-tabs :deep(.v-tab) {
  min-width: auto !important;
  font-size: 11px;
  font-weight: 700;
  text-transform: none;
  letter-spacing: 0;
  padding-inline: 10px !important;
}
.nav-subgrupo-topic {
  margin: 4px 12px 2px;
  font-size: 10px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.req-nav-list {
  max-height: calc(100vh - 300px);
  overflow-y: auto;
  padding-inline: 4px;
}
.nav-item {
  border-radius: 8px;
  margin-bottom: 2px;
}
.logout-item {
  color: var(--error) !important;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  min-width: 0;
}
.user-initials {
  font-size: 12px;
  font-weight: 700;
  color: #111;
}
.user-name {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.user-role {
  font-size: 11px;
}
.req-content-shell {
  min-width: 0;
  width: 100%;
}

@media (max-width: 600px) {
  .req-role-chip {
    max-width: 96px;
  }

  .req-main {
    padding-top: 56px;
  }
}
</style>
