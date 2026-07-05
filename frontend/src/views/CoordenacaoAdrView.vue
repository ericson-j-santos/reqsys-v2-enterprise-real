<template>
  <CoordenacaoDashboard
    base-path="/v1/agents/adr-orchestrator"
    variante="adr"
    titulo="Coordenação Geral de ADRs"
    subtitulo="Cada ADR (001 a 012) tem um coordenador especialista; a coordenação geral classifica a demanda, aponta ADRs relacionados e detecta violações de gate em tempo real."
  />
</template>

<script setup>
import CoordenacaoDashboard from '../components/CoordenacaoDashboard.vue'
</script>
