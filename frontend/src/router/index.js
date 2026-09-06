import { defineRouter } from '#q-app/wrappers'
import { createRouter, createMemoryHistory, createWebHistory, createWebHashHistory } from 'vue-router'
import { useAuthStore } from 'stores/auth'

const routes = [
  {
    path: '/login',
    component: () => import('pages/LoginPage.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('pages/DashboardPage.vue') },
      {
        path: 'plots',
        component: () => import('pages/PlotsPage.vue'),
        meta: { roles: ['chairman', 'treasurer', 'superadmin'] },
      },
      {
        path: 'members',
        component: () => import('pages/MembersPage.vue'),
        meta: { roles: ['chairman', 'treasurer', 'superadmin'] },
      },
      {
        path: 'billing',
        component: () => import('pages/BillingPage.vue'),
        meta: { roles: ['chairman', 'treasurer', 'superadmin'] },
      },
      {
        path: 'electricity',
        component: () => import('pages/ElectricityPage.vue'),
        meta: { roles: ['chairman', 'treasurer', 'superadmin'] },
      },
      {
        path: 'meter-reading',
        component: () => import('pages/MeterReadingPage.vue'),
      },
      {
        path: 'reports',
        component: () => import('pages/ReportsPage.vue'),
        meta: { roles: ['chairman', 'treasurer', 'superadmin'] },
      },
    ],
  },
  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue'),
  },
]

export default defineRouter(function ({ store }) {
  const createHistory = process.env.SERVER
    ? createMemoryHistory
    : (process.env.VUE_ROUTER_MODE === 'history' ? createWebHistory : createWebHashHistory)

  const router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,
    history: createHistory(process.env.VUE_ROUTER_BASE),
  })

  router.beforeEach(async (to) => {
    const auth = useAuthStore()

    if (to.meta.public) return true

    if (!auth.isAuthenticated) {
      if (to.path === '/login') return true
      return '/login'
    }

    if (to.meta.roles && !to.meta.roles.includes(auth.user?.role)) {
      return '/dashboard'
    }

    return true
  })

  return router
})
