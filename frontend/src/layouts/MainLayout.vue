<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated class="bg-green-8">
      <q-toolbar>
        <q-btn flat dense round icon="menu" @click="drawer = !drawer" />
        <q-toolbar-title>{{ pageTitle }}</q-toolbar-title>
        <q-btn flat dense round icon="account_circle" @click="profileMenu = true" />
      </q-toolbar>
    </q-header>

    <q-drawer v-model="drawer" :width="260" :breakpoint="600" show-if-above behavior="mobile" elevated>
      <q-scroll-area class="fit">
        <!-- Profil -->
        <div class="q-pa-md bg-green-8 text-white">
          <div class="text-subtitle1 text-weight-bold">{{ user?.full_name || user?.username }}</div>
          <div class="text-caption">{{ roleLabel }}</div>
          <div class="text-caption opacity-80">{{ user?.organization_name }}</div>
        </div>

        <q-list padding>
          <q-item clickable v-ripple to="/dashboard" exact>
            <q-item-section avatar><q-icon name="dashboard" /></q-item-section>
            <q-item-section>Главная</q-item-section>
          </q-item>

          <template v-if="!isMemberOnly">
            <q-separator spaced />
            <q-item-label header class="text-grey-7">Управление</q-item-label>

            <q-item clickable v-ripple to="/members">
              <q-item-section avatar><q-icon name="people" /></q-item-section>
              <q-item-section>Члены</q-item-section>
            </q-item>

            <q-item clickable v-ripple to="/plots">
              <q-item-section avatar><q-icon name="landscape" /></q-item-section>
              <q-item-section>Участки</q-item-section>
            </q-item>

            <q-separator spaced />
            <q-item-label header class="text-grey-7">Финансы</q-item-label>

            <q-item clickable v-ripple to="/billing">
              <q-item-section avatar><q-icon name="receipt_long" /></q-item-section>
              <q-item-section>Начисления</q-item-section>
            </q-item>

            <q-item clickable v-ripple to="/electricity">
              <q-item-section avatar><q-icon name="bolt" /></q-item-section>
              <q-item-section>Электроэнергия</q-item-section>
            </q-item>

            <q-item clickable v-ripple to="/reports">
              <q-item-section avatar><q-icon name="bar_chart" /></q-item-section>
              <q-item-section>Отчёты</q-item-section>
            </q-item>
          </template>

          <template v-if="isMemberOnly || isAuth">
            <q-separator spaced />
            <q-item-label header class="text-grey-7">Личный кабинет</q-item-label>

            <q-item clickable v-ripple to="/meter-reading">
              <q-item-section avatar><q-icon name="speed" /></q-item-section>
              <q-item-section>Показания счётчика</q-item-section>
            </q-item>
          </template>

          <q-separator spaced />
          <q-item clickable v-ripple @click="logout">
            <q-item-section avatar><q-icon name="logout" color="negative" /></q-item-section>
            <q-item-section class="text-negative">Выход</q-item-section>
          </q-item>
        </q-list>
      </q-scroll-area>
    </q-drawer>

    <q-page-container>
      <router-view />
    </q-page-container>

    <!-- Profile quick menu -->
    <q-dialog v-model="profileMenu" position="top">
      <q-card style="min-width: 300px">
        <q-card-section class="bg-green-8 text-white">
          <div class="text-h6">{{ user?.full_name || user?.username }}</div>
          <div class="text-caption">{{ roleLabel }} · {{ user?.organization_name }}</div>
        </q-card-section>
        <q-card-actions>
          <q-btn flat label="Закрыть" v-close-popup />
          <q-space />
          <q-btn flat color="negative" label="Выйти" @click="logout" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-layout>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from 'stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const drawer = ref(false)
const profileMenu = ref(false)

const user = computed(() => auth.user)
const isAuth = computed(() => auth.isAuthenticated)
const isMemberOnly = computed(() => auth.isMember)

const roleLabel = computed(() => {
  const map = {
    superadmin: 'Суперадмин',
    chairman: 'Председатель',
    treasurer: 'Казначей',
    member: 'Член СНТ',
  }
  return map[user.value?.role] || ''
})

const pageTitles = {
  '/dashboard': 'Главная',
  '/members': 'Члены СНТ',
  '/plots': 'Участки',
  '/billing': 'Начисления',
  '/electricity': 'Электроэнергия',
  '/meter-reading': 'Показания счётчика',
  '/reports': 'Отчёты',
}
const pageTitle = computed(() => pageTitles[route.path] || 'СНТ Платформа')

async function logout() {
  auth.logout()
  await router.push('/login')
}
</script>
