import { defineStore } from 'pinia'
import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || '/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: localStorage.getItem('access') || null,
    refreshToken: localStorage.getItem('refresh') || null,
    user: JSON.parse(localStorage.getItem('user') || 'null'),
  }),

  getters: {
    isAuthenticated: (s) => !!s.accessToken,
    isChairman: (s) => s.user?.role === 'chairman' || s.user?.role === 'superadmin',
    isTreasurer: (s) => ['chairman', 'treasurer', 'superadmin'].includes(s.user?.role),
    isMember: (s) => s.user?.role === 'member',
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
    },

    async fetchMe() {
      const { data } = await axios.get(`${BASE}/me/`, {
        headers: { Authorization: `Bearer ${this.accessToken}` },
      })
      this.user = data
      localStorage.setItem('user', JSON.stringify(data))
    },

    logout() {
      this.accessToken = null
      this.refreshToken = null
      this.user = null
      localStorage.removeItem('access')
      localStorage.removeItem('refresh')
      localStorage.removeItem('user')
    },
  },
})
