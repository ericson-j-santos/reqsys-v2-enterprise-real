<template>
  <!-- eslint-disable vue/no-multiple-template-root -->
  <!-- MOBILE APP BAR -->
  <v-app-bar v-if="mobile" :elevation="2" color="surface">
    <v-app-bar-nav-icon @click="mobileDrawer = !mobileDrawer" />
    <v-app-bar-title>
      <span class="text-primary font-weight-bold">ReqSys</span>
      <span class="text-caption text-medium-emphasis ml-2">Enterprise</span>
    </v-app-bar-title>
    <template #append>
      <v-avatar color="primary" size="36" class="mr-2">
        <span class="text-caption font-weight-bold text-background">
          {{ iniciais }}
        </span>
      </v-avatar>
    </template>
  </v-app-bar>

  <!-- SIDEBAR (temporary on mobile, permanent + rail toggle on desktop) -->
  <v-navigation-drawer
    v-model="drawerOpen"
    :rail="!mobile && railMode"
    :temporary="mobile"
    color="surface"
    :elevation="mobile ? 4 : 0"
    border="e"
  >
    <!-- Logo / Header -->
    <v-list-item
      v-if="!mobile"
      class="py-4"
      :prepend-icon="railMode ? 'mdi-layers-triple' : undefined"
    >
      <template v-if="!railMode">
        <v-list-item-title class="text-h6 font-weight-bold">
          <span class="text-primary">ReqSys</span>
          <span class="text-body-2 text-medium-emphasis ml-1">Enterprise</span>
        </v-list-item-title>
        <v-list-item-subtitle>v2.0 · Análise Ágil</v-list-item-subtitle>
      </template>
    </v-list-item>

    <v-divider v-if="!mobile" />

    <!-- Rail toggle button -->
    <div v-if="!mobile" class="d-flex justify-end pa-2">
      <v-btn
        :icon="railMode ? 'mdi-chevron-right' : 'mdi-chevron-left'"
        variant="text"
        size="small"
        @click="railMode = !railMode"
      />
    </div>

    <!-- Nav Items -->
    <v-list density="compact" nav class="mt-1">
      <v-tooltip
        v-for="item in navItems"
        :key="item.rota"
        :text="item.label"
        :disabled="!railMode"
        location="end"
      >
        <template #activator="{ props: ttProps }">
          <v-list-item
            v-bind="ttProps"
            :prepend-icon="item.icon"
            :title="item.label"
            :to="item.rota"
            :active="$route.path === item.rota"
            active-color="primary"
            rounded="lg"
            class="mb-1"
            :class="{ 'px-2': railMode }"
          />
        </template>
      </v-tooltip>
    </v-list>

    <!-- User + Logout (bottom) -->
    <template #append>
      <v-divider />
      <v-list density="compact" nav class="py-2">
        <v-list-item v-if="!railMode" :subtitle="auth.usuario?.papel || ''" class="py-2">
          <template #title>
            <span class="text-caption font-weight-medium">
              {{ auth.usuario?.nome || 'Usuário' }}
            </span>
          </template>
          <template #prepend>
            <v-avatar color="primary" size="32">
              <span class="text-caption font-weight-bold text-background">{{ iniciais }}</span>
            </v-avatar>
          </template>
        </v-list-item>
        <v-tooltip text="Sair" :disabled="!railMode" location="end">
          <template #activator="{ props: ttProps }">
            <v-list-item
              v-bind="ttProps"
              prepend-icon="mdi-logout"
              title="Sair"
              active-color="error"
              rounded="lg"
              @click="sair"
            />
          </template>
        </v-tooltip>
      </v-list>
    </template>
  </v-navigation-drawer>

  <!-- MAIN CONTENT -->
  <v-main>
    <!-- Breadcrumb bar (desktop only) -->
    <v-sheet v-if="!mobile && breadcrumbs.length" color="surface-variant" class="px-6 py-2">
      <v-breadcrumbs :items="breadcrumbs" density="compact" class="pa-0">
        <template #divider>
          <v-icon size="x-small">mdi-chevron-right</v-icon>
        </template>
      </v-breadcrumbs>
    </v-sheet>

    <v-container fluid class="pa-4 pa-md-6">
      <router-view />
    </v-container>
  </v-main>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useDisplay } from 'vuetify'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const { mobile } = useDisplay()
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const railMode = ref(false)
const mobileDrawer = ref(false)

const drawerOpen = computed({
  get: () => mobile.value ? mobileDrawer.value : true,
  set: (v) => { if (mobile.value) mobileDrawer.value = v }
})

const navItems = [
  { label: 'Dashboard',       icon: 'mdi-view-dashboard-outline',  rota: '/' },
  { label: 'Requisitos',      icon: 'mdi-clipboard-list-outline',   rota: '/requisitos' },
  { label: 'Pipeline',        icon: 'mdi-pipe',                      rota: '/pipeline' },
  { label: 'Qualidade IA',    icon: 'mdi-brain',                     rota: '/qualidade-ia' },
  { label: 'Relatórios SSRS', icon: 'mdi-chart-bar',                 rota: '/relatorios' },
  { label: 'Segredos',        icon: 'mdi-shield-key-outline',        rota: '/segredos-status' },
  { label: 'Rastreabilidade', icon: 'mdi-map-marker-path',           rota: '/rastreabilidade' },
  { label: 'Auditoria',       icon: 'mdi-history',                   rota: '/auditoria' },
  { label: 'Notificações',    icon: 'mdi-bell-outline',              rota: '/notificacoes' },
  { label: 'Hub Low-Code',   icon: 'mdi-layers-triple-outline',     rota: '/hub-lowcode' },
]

const iniciais = computed(() => {
  const nome = auth.usuario?.nome || ''
  return nome.split(' ').slice(0, 2).map(n => n[0] || '').join('').toUpperCase() || 'RS'
})

const breadcrumbs = computed(() => {
  const crumbs = [{ title: 'ReqSys', to: '/' }]
  const match = navItems.find(n => n.rota === route.path)
  if (match && route.path !== '/') crumbs.push({ title: match.label, disabled: true })
  return crumbs
})

function sair() {
  auth.sair()
  router.push('/login')
}
</script>
