<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated class="bg-green-8">
      <q-toolbar>
        <q-btn flat dense round icon="menu" @click="drawer = !drawer" />
        <q-toolbar-title>{{ pageTitle }}</q-toolbar-title>

        <!-- Выбор организации (только для суперадмина) -->
        <template v-if="auth.isSuperAdmin">
          <q-chip
            v-if="auth.selectedOrgName"
            icon="home_work"
            color="green-6"
            text-color="white"
            clickable
            @click="orgDialog = true"
            class="q-mr-xs"
          >
            {{ auth.selectedOrgName }}
          </q-chip>
          <q-btn
            v-else
            flat dense
            icon="home_work"
            label="Выбрать СНТ"
            color="yellow-4"
            @click="orgDialog = true"
            class="q-mr-xs text-caption"
          />
        </template>

        <q-btn flat dense round icon="account_circle" @click="profileMenu = true" />
      </q-toolbar>
    </q-header>

    <q-drawer v-model="drawer" :width="260" :breakpoint="600" show-if-above behavior="mobile" elevated>
      <q-scroll-area class="fit">
        <!-- Профиль -->
        <div class="q-pa-md bg-green-8 text-white">
          <div class="text-subtitle1 text-weight-bold">{{ user?.full_name || user?.username }}</div>
          <div class="text-caption">{{ roleLabel }}</div>
          <div class="text-caption opacity-80">{{ auth.selectedOrgName || user?.organization_name }}</div>
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

    <!-- Меню профиля -->
    <q-dialog v-model="profileMenu" position="top">
      <q-card style="min-width: 300px">
        <q-card-section class="bg-green-8 text-white">
          <div class="text-h6">{{ user?.full_name || user?.username }}</div>
          <div class="text-caption">{{ roleLabel }} · {{ auth.selectedOrgName || user?.organization_name }}</div>
        </q-card-section>
        <q-card-actions>
          <q-btn flat label="Закрыть" v-close-popup />
          <q-space />
          <q-btn flat color="negative" label="Выйти" @click="logout" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Диалог выбора / создания организации (суперадмин) -->
    <q-dialog v-model="orgDialog" persistent>
      <q-card style="min-width: 380px; max-width: 480px">
        <q-card-section class="bg-green-8 text-white row items-center">
          <q-icon name="home_work" size="24px" class="q-mr-sm" />
          <span class="text-h6">Выбор организации (СНТ)</span>
        </q-card-section>

        <q-card-section>
          <div v-if="orgsLoading" class="text-center q-pa-md">
            <q-spinner color="green-8" size="32px" />
          </div>

          <q-list separator v-else-if="orgs.length">
            <q-item
              v-for="o in orgs"
              :key="o.id"
              clickable
              v-ripple
              :active="auth.selectedOrgId === String(o.id)"
              active-class="bg-green-1"
              @click="selectOrg(o)"
            >
              <q-item-section avatar>
                <q-icon name="park" color="green-8" />
              </q-item-section>
              <q-item-section>
                <q-item-label>{{ o.name }}</q-item-label>
                <q-item-label caption>{{ o.legal_address || o.inn || '—' }}</q-item-label>
              </q-item-section>
              <q-item-section side v-if="auth.selectedOrgId === String(o.id)">
                <q-icon name="check_circle" color="green-8" />
              </q-item-section>
            </q-item>
          </q-list>

          <div v-else class="text-grey-6 text-center q-pa-md">Организации не найдены</div>
        </q-card-section>

        <!-- Форма создания новой организации -->
        <q-expansion-item icon="add" label="Создать новую организацию" class="q-mx-md q-mb-sm">
          <q-card flat bordered>
            <q-card-section class="q-gutter-sm">
              <q-input v-model="newOrg.name" label="Название СНТ *" outlined dense />
              <q-input v-model="newOrg.inn" label="ИНН" outlined dense maxlength="12" />
              <q-input v-model="newOrg.legal_address" label="Юридический адрес" outlined dense />
              <q-btn
                color="green-8"
                label="Создать"
                :loading="creatingOrg"
                :disable="!newOrg.name"
                @click="createOrg"
                unelevated
                class="full-width"
              />
            </q-card-section>
          </q-card>
        </q-expansion-item>

        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-layout>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useQuasar } from 'quasar'
import { useAuthStore } from 'stores/auth'
import api from 'src/api/client'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const $q = useQuasar()

const drawer = ref(false)
const profileMenu = ref(false)
const orgDialog = ref(false)
const orgsLoading = ref(false)
const creatingOrg = ref(false)
const orgs = ref([])
const newOrg = ref({ name: '', inn: '', legal_address: '' })

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

async function loadOrgs() {
  orgsLoading.value = true
  try {
    const { data } = await api.get('/organizations/')
    orgs.value = data.results || data
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Не удалось загрузить организации' })
  } finally {
    orgsLoading.value = false
  }
}

function selectOrg(o) {
  auth.setOrg(o.id, o.name)
  orgDialog.value = false
  $q.notify({ type: 'positive', message: `Организация: ${o.name}` })
  // Перегружаем текущую страницу чтобы данные обновились
  router.go(0)
}

async function createOrg() {
  if (!newOrg.value.name) return
  creatingOrg.value = true
  try {
    const { data } = await api.post('/organizations/', newOrg.value)
    orgs.value.push(data)
    newOrg.value = { name: '', inn: '', legal_address: '' }
    selectOrg(data)
    $q.notify({ type: 'positive', message: 'Организация создана' })
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Ошибка создания организации' })
  } finally {
    creatingOrg.value = false
  }
}

// Открытие диалога: загружаем список орг
watch(orgDialog, (val) => {
  if (val) loadOrgs()
})

async function logout() {
  auth.logout()
  await router.push('/login')
}

</script>
