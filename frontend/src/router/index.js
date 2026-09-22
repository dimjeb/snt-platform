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
    // Вне MainLayout: пока пароль временный, показывать меню разделов
    // бессмысленно — API на них всё равно отвечает 403.
    path: '/change-password',
    component: () => import('pages/ChangePasswordPage.vue'),
    meta: { requiresAuth: true },
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
        path: 'statements',
        component: () => import('pages/StatementPage.vue'),
        meta: { roles: ['chairman', 'treasurer', 'superadmin'] },
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

    // Временный пароль: до смены не пускаем никуда, кроме самой смены.
    // Сервер это тоже проверяет (PasswordChangeRequiredMiddleware), здесь
    // лишь чтобы человек видел форму, а не череду ошибок доступа.
    if (auth.user?.must_change_password) {
      return to.path === '/change-password' ? true : '/change-password'
    }
    if (to.path === '/change-password') return true

    if (to.meta.roles && !to.meta.roles.includes(auth.user?.role)) {
      return '/dashboard'
    }

    return true
  })

  // Страницы грузятся по требованию, отдельными файлами с хешем в имени.
  // Если вкладка открыта со старого index.html, а на сервере уже новая
  // сборка, такого файла на диске нет — импорт падает, и пользователь
  // видит белый экран. Единственное верное лечение — перезагрузить
  // документ целиком: тогда придёт свежий index.html с новыми именами.
  router.onError((error, to) => {
    const message = String(error?.message || '')
    const chunkGone = (
      message.includes('Failed to fetch dynamically imported module')
      || message.includes('Importing a module script failed')
      || message.includes('error loading dynamically imported module')
    )
    if (chunkGone && to?.fullPath) {
      window.location.assign(to.fullPath)
    }
  })

  return router
})
