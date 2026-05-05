<template>
  <v-app>
    <AppLayout v-if="$route.path !== '/login'" />
    <router-view v-else />
  </v-app>
</template>

<script setup>
import AppLayout from './layouts/AppLayout.vue'
</script>
