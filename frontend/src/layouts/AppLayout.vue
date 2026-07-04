<template>
  <v-layout class="req-layout">
    <v-app-bar v-if="mobile" flat class="req-appbar" elevation="0" height="56">
      <v-app-bar-nav-icon color="white" aria-label="Abrir menu de navegacao" @click="drawer = !drawer" />
      <span class="brand-sm ml-1"><span class="brand-dot brand-dot--sm">R</span> ReqSys</span>
      <AmbienteNavigator
        :environment-hint="environment"
        compact
        :show-prefix="false"
        class="ml-2"
      />
      <v-spacer />
      <v-chip size="x-small" color="amber" variant="tonal" class="mr-2 req-role-chip">
        {{ auth.usuario?.papel || 'user' }}
        <v-tooltip
          activator="parent"
          location="bottom"
          text="Seu perfil define permissoes de leitura, edicao, auditoria e acoes administrativas."
        />
      </v-chip>
      <v-btn
        icon
        variant="text"
        color="white"
        :aria-label="temaClaro ? 'Ativar tema escuro' : 'Ativar tema claro'"
        @click="alternarTemaVisual"
      >
        <v-icon :icon="temaClaro ? 'mdi-weather-night' : 'mdi-white-balance-sunny'" />
        <v-tooltip
          activator="parent"
          location="bottom"
          :text="temaClaro ? 'Alterna para o tema escuro. A preferencia fica salva neste navegador.' : 'Alterna para o tema claro. A preferencia fica salva neste navegador.'"
        />
      </v-btn>
    </v-app-bar>

    <v-navigation-drawer
      v-model="drawer"
      :permanent="!mobile"
      :temporary="mobile"
      width="312"
      class="req-drawer"
    >
      <div class="pa-5 pb-3 req-brand-block">
        <div class="brand"><span class="brand-dot">R</span> ReqSys Enterprise</div>
        <div class="muted mt-1 version-line" data-testid="app-version-label">
          {{ versionLabel }}
          <v-tooltip
            activator="parent"
            location="bottom"
            text="Versao carregada no navegador e versao informada pela API. Ajuda a identificar cache ou deploy parcial."
          />
        </div>
        <v-chip
          v-if="hasVersionDrift"
          size="x-small"
          color="warning"
          variant="tonal"
          class="mt-1"
          prepend-icon="mdi-alert-outline"
          data-testid="app-version-drift-chip"
        >
          Versoes divergentes
          <v-tooltip
            activator="parent"
            location="bottom"
            text="O frontend e a API parecem estar em versoes diferentes. Atualize a pagina ou valide o deploy do ambiente."
          />
        </v-chip>
        <AmbienteNavigator
          :environment-hint="environment"
          compact
          class="mt-2 d-inline-block"
        />
        <v-btn
          block
          variant="tonal"
          color="primary"
          class="theme-toggle mt-3"
          :prepend-icon="temaClaro ? 'mdi-weather-night' : 'mdi-white-balance-sunny'"
          :aria-label="temaClaro ? 'Ativar tema escuro' : 'Ativar tema claro'"
          @click="alternarTemaVisual"
        >
          {{ temaClaro ? 'Tema escuro' : 'Tema claro' }}
          <v-tooltip
            activator="parent"
            location="right"
            :text="temaClaro ? 'Volta para a interface escura, indicada para baixa luminosidade e uso prolongado.' : 'Muda para a interface clara, indicada para leitura em ambientes iluminados.'"
          />
        </v-btn>
      </div>
      <v-divider />

      <v-list
        v-model:opened="temasAbertos"
        density="compact"
        nav
        class="pt-2 req-nav-list"
        aria-label="Navegacao por temas expansiveis"
      >
        <v-list-group
          v-for="tema in NAV_TEMAS"
          :key="tema.id"
          :value="tema.id"
        >
          <template #activator="{ props }">
            <v-list-item
              v-bind="props"
              :prepend-icon="tema.icon"
              class="nav-theme-item"
              :class="{ 'nav-theme-item--active': tema.id === temaAtivo }"
              :data-testid="`nav-tema-${tema.id}`"
              @click="selecionarTema(tema.id)"
            >
              <v-list-item-title>{{ tema.title }}</v-list-item-title>
              <v-list-item-subtitle>{{ tema.topic }}</v-list-item-subtitle>
              <v-tooltip
                activator="parent"
                location="right"
                :text="tooltipTema(tema)"
              />
              <template #append>
                <span
                  v-if="badgeTema(tema.id).count > 0"
                  class="nav-tema-badge"
                  :class="`nav-tema-badge--${badgeTema(tema.id).level}`"
                  :data-testid="`nav-badge-${tema.id}`"
                  :title="`${badgeTema(tema.id).count} pendencia(s)`"
                >
                  {{ badgeLabel(badgeTema(tema.id).count) }}
                  <v-tooltip
                    activator="parent"
                    location="right"
                    :text="tooltipBadge(tema.id)"
                  />
                </span>
              </template>
            </v-list-item>
          </template>

          <div v-if="temaTemSubgrupos(tema.id)" class="nav-subgroup-stack">
            <div
              v-for="sub in tema.subgroups"
              :key="sub.id"
              class="nav-subgroup"
              :data-testid="`nav-subgrupo-${sub.id}`"
            >
              <button
                class="nav-subgroup-header"
                :class="{ 'nav-subgroup-header--active': tema.id === temaAtivo && sub.id === subgrupoAtivo }"
                type="button"
                @click="selecionarSubgrupo(tema.id, sub.id)"
              >
                <span>{{ sub.title }}</span>
                <small>{{ sub.topic }}</small>
                <v-tooltip
                  activator="parent"
                  location="right"
                  :text="tooltipSubgrupo(sub)"
                />
              </button>
              <v-tooltip
                v-for="item in itensDoSubgrupo(tema.id, sub.id)"
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
                    class="nav-item nav-item--nested"
                    :data-testid="`nav-item-${navItemTestId(item.to)}`"
                    @click="mobile && (drawer = false)"
                  />
                </template>
              </v-tooltip>
            </div>
          </div>

          <v-tooltip
            v-for="item in tema.items"
            v-else
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
                class="nav-item nav-item--nested"
                :data-testid="`nav-item-${navItemTestId(item.to)}`"
                @click="mobile && (drawer = false)"
              />
            </template>
          </v-tooltip>
        </v-list-group>
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
          <v-tooltip
            activator="parent"
            location="top"
            text="Usuario autenticado e papel ativo nesta sessao."
          />
        </div>
        <v-list density="compact" class="pb-2">
          <v-list-item
            prepend-icon="mdi-logout"
            title="Sair"
            class="nav-item logout-item"
            @click="sair"
          >
            <v-tooltip
              activator="parent"
              location="right"
              text="Encerra sua sessao neste navegador e volta para a tela de login."
            />
          </v-list-item>
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
import { useDisplay, useTheme } from 'vuetify'
import { useAuthStore } from '../stores/auth'
import { api } from '../services/api'
import AmbienteNavigator from '../components/AmbienteNavigator.vue'
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
  subgrupoIdPorRota,
  temaIdPorRota,
  temaPorId,
  temaTemSubgrupos,
} from '../constants/navCatalog'
import { useAppVersion } from '../composables/useAppVersion'

const { mobile } = useDisplay()
const theme = useTheme()
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
const temasAbertos = ref([temaAtivo.value])
const temaAtual = computed(() => temaPorId(temaAtivo.value))
const temaClaro = computed(() => theme.global.name.value === 'reqsysClaro')

watch(mobile, (isMobile) => {
  drawer.value = !isMobile
})

watch(temaAtivo, (id) => {
  salvarTemaPersistido(id)
  if (!temasAbertos.value.includes(id)) temasAbertos.value = [...temasAbertos.value, id]
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
    if (!temasAbertos.value.includes(temaAtivo.value)) {
      temasAbertos.value = [...temasAbertos.value, temaAtivo.value]
    }
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
      if (!temasAbertos.value.includes(persistido)) {
        temasAbertos.value = [...temasAbertos.value, persistido]
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

function tooltipTema(tema) {
  const total = tema.items?.length ?? 0
  const pendencias = badgeTema(tema.id).count
  const complemento = pendencias > 0 ? ` Ha ${pendencias} ponto(s) de atencao nesta area.` : ''
  return `${tema.title}: ${tema.topic}. Expanda para ver ${total} tela(s) relacionadas sem perder o contexto.${complemento}`
}

function tooltipBadge(temaId) {
  const badge = badgeTema(temaId)
  if (!badge.count) return 'Sem pendencias sinalizadas nesta area.'
  const gravidade = badge.level === 'vermelho' ? 'criticas' : 'de atencao'
  return `${badge.count} pendencia(s) ${gravidade} calculadas a partir dos dados operacionais do ReqSys.`
}

function tooltipSubgrupo(sub) {
  return `${sub.title}: ${sub.topic}. Use este agrupamento para entender a etapa do fluxo antes de abrir uma tela especifica.`
}

function selecionarTema(temaId) {
  temaAtivo.value = temaId
}

function selecionarSubgrupo(temaId, subgrupoId) {
  temaAtivo.value = temaId
  subgrupoAtivo.value = subgrupoId
}

function alternarTemaVisual() {
  const proximo = temaClaro.value ? 'figmaPadraoOuro' : 'reqsysClaro'
  theme.global.name.value = proximo
  localStorage.setItem('reqsys_tema_visual', proximo)
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
.theme-toggle {
  justify-content: flex-start;
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
.nav-theme-item {
  border-radius: 10px;
  margin: 2px 6px;
  border: 1px solid transparent;
}
.nav-theme-item--active {
  border-color: rgba(243, 146, 0, 0.38);
  background: rgba(243, 146, 0, 0.1);
}
.nav-subgroup-stack {
  padding: 2px 8px 8px 20px;
}
.nav-subgroup {
  border-left: 1px solid var(--line);
  padding-left: 8px;
  margin-left: 2px;
}
.nav-subgroup-header {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--text);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
}
.nav-subgroup-header span {
  font-size: 12px;
  font-weight: 800;
}
.nav-subgroup-header small {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.25;
}
.nav-subgroup-header--active,
.nav-subgroup-header:hover {
  background: rgba(56, 189, 248, 0.1);
}
.req-nav-list {
  max-height: calc(100vh - 260px);
  overflow-y: auto;
  padding-inline: 4px;
}
.nav-item {
  border-radius: 8px;
  margin-bottom: 2px;
}
.nav-item--nested {
  margin-left: 4px;
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
