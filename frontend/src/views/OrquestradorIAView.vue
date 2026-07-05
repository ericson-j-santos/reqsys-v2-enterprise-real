<template>
  <CoordenacaoDashboard
    base-path="/v1/agents/orchestrator"
    variante="tematico"
    titulo="Orquestrador IA por Tema"
    subtitulo="Classifica uma demanda e aciona o coordenador de IA responsável por runtime, CI/CD, agile, GovBI, IA/RAG, segurança, UX ou arquitetura."
  />
</template>

<script setup>
import CoordenacaoDashboard from '../components/CoordenacaoDashboard.vue'
</script>
