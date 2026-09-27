import { defineStore } from 'pinia'
import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || '/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: localStorage.getItem('access') || null,
    refreshToken: localStorage.getItem('refresh') || null,
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    // Для суперадмина: выбранная организация
    selectedOrgId: localStorage.getItem('selectedOrgId') || null,
    selectedOrgName: localStorage.getItem('selectedOrgName') || null,
  }),

  getters: {
    isAuthenticated: (s) => !!s.accessToken,
    isChairman: (s) => s.user?.role === 'chairman' || s.user?.role === 'superadmin',
    isTreasurer: (s) => ['chairman', 'treasurer', 'superadmin'].includes(s.user?.role),
    isMember: (s) => s.user?.role === 'member',
    // Председатель и казначей обычно тоже владеют участком, и свои
    // начисления им нужно видеть так же, как всем. Личный кабинет
    // положен не по роли, а по связи учётки с членом СНТ.
    hasOwnCabinet: (s) => !!s.user?.member_id,
    isSuperAdmin: (s) => s.user?.role === 'superadmin',
    // Есть ли активный контекст организации
    hasOrg: (s) => !!(s.user?.organization || s.selectedOrgId),
  },

  actions: {
    async login(username, password) {
      const { data } = await axios.post(`${BASE}/auth/token/`, { username, password })
      this.accessToken = data.access
      this.refreshToken = data.refresh
      localStorage.setItem('access', data.access)
      localStorage.setItem('refresh', data.refresh)
      await this.fetchMe()
    },

    async refresh() {
      const { data } = await axios.post(`${BASE}/auth/token/refresh/`, {
        refresh: this.refreshToken,
      })
      this.accessToken = data.access
      localStorage.setItem('access', data.access)
      // Сервер ротирует refresh и гасит старый в чёрном списке. Если не
      // сохранить новый, следующее обновление пойдёт со сгоревшим токеном
      // и выкинет человека из системы посреди работы.
      if (data.refresh) {
        this.refreshToken = data.refresh
        localStorage.setItem('refresh', data.refresh)
      }
    },

    async fetchMe() {
      const { data } = await axios.get(`${BASE}/me/`, {
        headers: { Authorization: `Bearer ${this.accessToken}` },
      })
      this.user = data
      localStorage.setItem('user', JSON.stringify(data))
    },

    setOrg(id, name) {
      this.selectedOrgId = String(id)
      this.selectedOrgName = name
      localStorage.setItem('selectedOrgId', String(id))
      localStorage.setItem('selectedOrgName', name)
    },

    clearOrg() {
      this.selectedOrgId = null
      this.selectedOrgName = null
      localStorage.removeItem('selectedOrgId')
      localStorage.removeItem('selectedOrgName')
    },

    logout() {
      this.accessToken = null
      this.refreshToken = null
      this.user = null
      this.clearOrg()
      localStorage.removeItem('access')
      localStorage.removeItem('refresh')
      localStorage.removeItem('user')
    },
  },
})
