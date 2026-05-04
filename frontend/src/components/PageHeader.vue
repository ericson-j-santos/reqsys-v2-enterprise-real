<!--
  PageHeader — componente padrão de cabeçalho de página.

  Props:
    title    (String, obrigatório) — título principal h1
    subtitle (String)             — texto descritivo abaixo do título
    chip     (String)             — texto do chip de status/badge lateral
    chipColor (String)            — cor Vuetify do chip (padrão: 'amber')
    chipTooltip (String)          — tooltip do chip

  Slot "actions":
    Botões de ação do cabeçalho (Atualizar, Novo, etc.)

  Exemplos:
    <PageHeader title="Requisitos" subtitle="Cadastre e acompanhe solicitações.">
      <template #actions>
        <v-btn ...>Atualizar</v-btn>
      </template>
    </PageHeader>

    <PageHeader title="Pipeline" subtitle="..." chip="Demo" chip-color="blue" chip-tooltip="Dados simulados" />
-->
<template>
  <div class="page-header">
    <div class="page-header__title-block">
      <h1>{{ title }}</h1>
      <p v-if="subtitle" class="muted page-header__subtitle">{{ subtitle }}</p>
    </div>
    <div class="page-header__actions">
      <slot name="actions" />
      <v-tooltip v-if="chip" :text="chipTooltip || chip" location="top">
        <template #activator="{ props }">
          <v-chip v-bind="props" size="small" :color="chipColor" variant="tonal">
            {{ chip }}
          </v-chip>
        </template>
      </v-tooltip>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  chip: { type: String, default: '' },
  chipColor: { type: String, default: 'amber' },
  chipTooltip: { type: String, default: '' },
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 24px;
}

.page-header__title-block h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1.3;
}

.page-header__subtitle {
  margin: 4px 0 0;
  max-width: 60ch;
}

.page-header__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
