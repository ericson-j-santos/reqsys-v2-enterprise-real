<template>
  <section class="page">
    <div class="page-header"><h1>Requisitos</h1><v-btn color="amber" @click="dialog=true">Novo requisito</v-btn></div>
    <v-skeleton-loader v-if="store.carregando" type="table" />
    <v-data-table v-else :headers="headers" :items="store.itens" item-value="id" class="table-card">
      <template #item.status="{ item }"><v-chip size="small" :color="corStatus(item.status)">{{ item.status }}</v-chip></template>
    </v-data-table>
    <v-dialog v-model="dialog" width="760">
      <v-card><v-card-title>Nova solicitação de requisito</v-card-title><v-card-text>
        <v-row><v-col cols="12" md="6"><v-text-field v-model="form.titulo" label="Título" /></v-col><v-col cols="12" md="6"><v-select v-model="form.urgencia" label="Urgência" :items="['baixa','media','alta','critica']" /></v-col></v-row>
        <v-textarea v-model="form.descricao" label="Descrição" />
        <v-row><v-col cols="12" md="4"><v-text-field v-model="form.area" label="Área" /></v-col><v-col cols="12" md="4"><v-text-field v-model="form.sistema" label="Sistema" /></v-col><v-col cols="12" md="4"><v-text-field v-model="form.solicitante" label="Solicitante" /></v-col></v-row>
      </v-card-text><v-card-actions><v-spacer/><v-btn variant="text" @click="dialog=false">Cancelar</v-btn><v-btn color="amber" @click="salvar">Salvar</v-btn></v-card-actions></v-card>
    </v-dialog>
  </section>
</template>
<script setup>
import { reactive, ref, onMounted } from 'vue'; import { useRequisitosStore } from '../stores/requisitos'
const store = useRequisitosStore(); const dialog = ref(false)
const form = reactive({ titulo:'Consulta prévia antes do cadastro rural', descricao:'Ao informar CPF ou CNPJ, verificar se cliente já existe antes de criar novo cadastro.', urgencia:'alta', area:'Crédito', sistema:'Portal Rural', solicitante:'gerencia_credito' })
const headers = [{title:'Código',key:'codigo'}, {title:'Título',key:'titulo'}, {title:'Status',key:'status'}, {title:'Urgência',key:'urgencia'}, {title:'Área',key:'area'}]
onMounted(store.listar)
function corStatus(s){ return ({recebido:'blue', em_analise:'orange', aprovado:'green', rejeitado:'red'})[s] || 'grey' }
async function salvar(){ await store.criar({...form}); dialog.value=false }
</script>
