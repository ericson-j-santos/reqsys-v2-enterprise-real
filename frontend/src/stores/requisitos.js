import { defineStore } from 'pinia'
import { api } from '../services/api'

export const useRequisitosStore = defineStore('requisitos', {
  state: () => ({
    itens: [],
    metricas: {},
    dashboardInfo: {},
    carregando: false,
    erro: null,
  }),
  actions: {
    async listar() {
      this.carregando = true
      try { this.itens = (await api.get('/v1/requisitos')).data.data }
      catch (e) { this.erro = e.message }
      finally { this.carregando = false }
    },
    async criar(payload) {
      const { data } = await api.post('/v1/requisitos', payload)
      this.itens.unshift(data.data)
      return data.data
    },
    async carregarMetricas() {
      this.carregando = true
      this.erro = null
      try {
        this.metricas = (await api.get('/v1/dashboard/requisitos')).data.data
      } catch (e) {
        this.erro = e.message
      } finally {
        this.carregando = false
      }
    },
    async carregarDashboardInfo() {
      this.carregando = true
      this.erro = null
      try {
        this.dashboardInfo = (await api.get('/v1/dashboard/info')).data.data
      } catch (e) {
        this.erro = e.message
      } finally {
        this.carregando = false
      }
    }
  }
})
