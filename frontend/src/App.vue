<template>
  <v-app>
    <RouteFeedback v-if="$route.path !== '/login'" />
    <AppLayout v-if="$route.path !== '/login'" />
    <router-view v-else />
  </v-app>
</template>
<script setup>
import AppLayout from './layouts/AppLayout.vue'
import RouteFeedback from './components/RouteFeedback.vue'
</script>
