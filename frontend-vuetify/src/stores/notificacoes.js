import { defineStore } from 'pinia'
import { notificacoesService } from '../services/notificacoes'

export const useNotificacoesStore = defineStore('notificacoes', {
  state: () => ({
    dashboard: null,
    fila: [],
    dlq: [],
    logs: [],
    carregandoDashboard: false,
    carregandoFila: false,
    carregandoDlq: false,
    carregandoLogs: false,
    erro: null,
  }),

  actions: {
    async carregarDashboard() {
      this.carregandoDashboard = true
      try {
        this.dashboard = await notificacoesService.obterDashboard()
      } catch (e) {
        this.dashboard = { pendentes: 0, processando: 0, enviados: 0, falhas: 0 }
        this.erro = e?.response?.data?.errors?.[0]?.message || e.message
      } finally {
        this.carregandoDashboard = false
      }
    },

    async carregarFila(status = null) {
      this.carregandoFila = true
      try {
        this.fila = await notificacoesService.listarFila(status)
      } catch (e) {
        this.fila = []
        this.erro = e?.response?.data?.errors?.[0]?.message || e.message
      } finally {
        this.carregandoFila = false
      }
    },

    async carregarDlq() {
      this.carregandoDlq = true
      try {
        this.dlq = await notificacoesService.listarDlq()
      } catch (e) {
        this.dlq = []
        this.erro = e?.response?.data?.errors?.[0]?.message || e.message
      } finally {
        this.carregandoDlq = false
      }
    },

    async carregarLogs() {
      this.carregandoLogs = true
      try {
        this.logs = await notificacoesService.listarLogs()
      } catch (e) {
        this.logs = []
        this.erro = e?.response?.data?.errors?.[0]?.message || e.message
      } finally {
        this.carregandoLogs = false
      }
    },

    async carregarTudo() {
      this.erro = null
      await Promise.all([
        this.carregarDashboard(),
        this.carregarFila(),
        this.carregarDlq(),
        this.carregarLogs(),
      ])
    },

    async reprocessarDlq(idDlq) {
      await notificacoesService.reprocessarDlq(idDlq)
      await this.carregarTudo()
    },
  },
})
