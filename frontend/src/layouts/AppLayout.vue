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
      <!-- Brand -->
      <div class="pa-5 pb-3 req-brand-block">
        <div class="brand"><span class="brand-dot">R</span> ReqSys Enterprise</div>
        <div class="muted mt-1">SaaS Interno · v2 Enterprise</div>
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
            <v-icon :icon="tema.icon" size="16" class="mr-1" />
            <span class="nav-tema-label">{{ tema.title }}</span>
          </v-tab>
        </v-tabs>
        <p class="nav-tema-topic muted">{{ temaAtual.topic }}</p>
      </div>

      <!-- Sub-abas (rotas do tema) -->
      <v-list density="compact" nav class="pt-1 req-nav-list" aria-label="Navegação do tema">
        <v-tooltip
          v-for="item in temaAtual.items"
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
              :data-testid="`nav-item-${item.to.replace(/\//g, '').replace(/^$/, 'dashboard')}`"
              @click="mobile && (drawer = false)"
            />
          </template>
        </v-tooltip>
      </v-list>

      <!-- User + logout -->
      <template #append>
        <v-divider />
        <div v-if="auth.usuario" class="user-info">
          <v-avatar size="30" color="amber" aria-hidden="true">
            <span class="user-initials">
              {{ initials(auth.usuario) }}
            </span>
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
import { NAV_TEMAS, temaIdPorRota, temaPorId } from '../constants/navCatalog'

const { mobile } = useDisplay()
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const drawer = ref(!mobile.value)
const environment = ref(import.meta.env.VITE_APP_ENVIRONMENT || '')
const temaAtivo = ref(temaIdPorRota(route.path))

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

watch(mobile, (isMobile) => {
  drawer.value = !isMobile
})

watch(
  () => route.path,
  (path) => {
    temaAtivo.value = temaIdPorRota(path)
  },
)

onMounted(async () => {
  try {
    const { data } = await api.get('/v1/auth/config')
    if (data?.data?.environment) environment.value = data.data.environment
  } catch {
    // Mantem fallback do build quando a API publica nao estiver disponivel.
  }
})

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
.nav-temas {
  padding: 8px 8px 0;
}
.nav-temas-tabs :deep(.v-slide-group__content) {
  gap: 2px;
}
.nav-tema-tab {
  min-width: auto !important;
  padding-inline: 8px !important;
  font-size: 11px;
  font-weight: 700;
  text-transform: none;
  letter-spacing: 0;
}
.nav-tema-label {
  max-width: 72px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nav-tema-topic {
  margin: 6px 12px 4px;
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
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
