<template>
  <q-layout view="lHh LpR lFf">
    <q-header elevated class="snt-header">
      <q-toolbar class="snt-toolbar">
        <q-btn flat dense round icon="menu" @click="drawer = !drawer" class="q-mr-sm" />

        <div class="snt-logo row items-center no-wrap q-mr-md gt-xs">
          <q-icon name="park" size="22px" class="q-mr-xs" style="color:rgba(255,255,255,0.85)" />
          <span class="text-weight-bold" style="font-size:15px;letter-spacing:0.02em">СНТ Платформа</span>
        </div>

        <div class="snt-page-title lt-sm">{{ pageTitle }}</div>

        <q-space />

        <!-- Выбор организации (только суперадмин) -->
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

        <!-- Текущая страница (только md+) -->
        <div class="text-body2 q-mr-md gt-sm" style="opacity:0.75">{{ pageTitle }}</div>

        <q-btn flat dense round icon="account_circle" @click="profileMenu = true">
          <q-tooltip>{{ user?.full_name || user?.username }}</q-tooltip>
        </q-btn>
      </q-toolbar>
    </q-header>

    <!-- Боковая панель: на десктопе persistent, на мобиле overlay -->
    <q-drawer
      v-model="drawer"
      :width="240"
      :breakpoint="768"
      show-if-above
      class="snt-drawer"
      bordered
    >
      <q-scroll-area class="fit">
        <!-- Профиль в шапке ящика -->
        <div class="snt-drawer-profile">
          <div class="snt-avatar">
            {{ avatarLetter }}
          </div>
          <div class="snt-drawer-profile-info">
            <div class="text-subtitle2 text-weight-bold ellipsis">
              {{ user?.full_name || user?.username }}
            </div>
            <div class="text-caption snt-role-chip">{{ roleLabel }}</div>
            <div class="text-caption ellipsis" style="opacity:0.6;font-size:11px">
              {{ auth.selectedOrgName || user?.organization_name }}
            </div>
          </div>
        </div>

        <q-list padding class="snt-nav-list">
          <q-item clickable v-ripple to="/dashboard" exact class="snt-nav-item">
            <q-item-section avatar><q-icon name="dashboard" /></q-item-section>
            <q-item-section>Главная</q-item-section>
          </q-item>

          <template v-if="!isMemberOnly">
            <div class="snt-nav-group-label">Управление</div>

            <q-item clickable v-ripple to="/members" class="snt-nav-item">
              <q-item-section avatar><q-icon name="people" /></q-item-section>
              <q-item-section>Члены СНТ</q-item-section>
            </q-item>

            <q-item clickable v-ripple to="/plots" class="snt-nav-item">
              <q-item-section avatar><q-icon name="landscape" /></q-item-section>
              <q-item-section>Участки</q-item-section>
            </q-item>

            <div class="snt-nav-group-label">Финансы</div>

            <q-item clickable v-ripple to="/billing" class="snt-nav-item">
              <q-item-section avatar><q-icon name="receipt_long" /></q-item-section>
              <q-item-section>Начисления</q-item-section>
            </q-item>

            <q-item clickable v-ripple to="/electricity" class="snt-nav-item">
              <q-item-section avatar><q-icon name="bolt" /></q-item-section>
              <q-item-section>Электроэнергия</q-item-section>
            </q-item>

            <q-item clickable v-ripple to="/statements" class="snt-nav-item">
              <q-item-section avatar><q-icon name="account_balance" /></q-item-section>
              <q-item-section>Банковская выписка</q-item-section>
            </q-item>

            <q-item clickable v-ripple to="/reports" class="snt-nav-item">
              <q-item-section avatar><q-icon name="bar_chart" /></q-item-section>
              <q-item-section>Отчёты</q-item-section>
            </q-item>
          </template>

          <div class="snt-nav-group-label">Личный кабинет</div>

          <q-item clickable v-ripple to="/meter-reading" class="snt-nav-item">
            <q-item-section avatar><q-icon name="speed" /></q-item-section>
            <q-item-section>Показания счётчика</q-item-section>
          </q-item>

          <q-item clickable v-ripple to="/change-password" class="snt-nav-item">
            <q-item-section avatar><q-icon name="lock_reset" /></q-item-section>
            <q-item-section>Сменить пароль</q-item-section>
          </q-item>

          <!-- Django Admin — только для суперадмина -->
          <template v-if="auth.isSuperAdmin">
            <div class="snt-nav-group-label">Система</div>
            <q-item
              clickable v-ripple
              tag="a"
              href="/admin/"
              target="_blank"
              class="snt-nav-item"
            >
              <q-item-section avatar>
                <q-icon name="admin_panel_settings" />
              </q-item-section>
              <q-item-section>Django Admin</q-item-section>
              <q-item-section side>
                <q-icon name="open_in_new" size="14px" style="opacity:0.45" />
              </q-item-section>
            </q-item>
          </template>

          <q-separator spaced class="snt-separator" />

          <q-item clickable v-ripple @click="logout" class="snt-nav-item snt-logout">
            <q-item-section avatar><q-icon name="logout" /></q-item-section>
            <q-item-section>Выход</q-item-section>
          </q-item>
        </q-list>
      </q-scroll-area>
    </q-drawer>

    <q-page-container>
      <router-view />
    </q-page-container>

    <!-- Профиль диалог -->
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

    <!-- Диалог выбора организации (суперадмин) -->
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
              clickable v-ripple
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

const avatarLetter = computed(() => {
  const name = user.value?.full_name || user.value?.username || '?'
  return name[0].toUpperCase()
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
  } catch {
    $q.notify({ type: 'negative', message: 'Не удалось загрузить организации' })
  } finally {
    orgsLoading.value = false
  }
}

function selectOrg(o) {
  auth.setOrg(o.id, o.name)
  orgDialog.value = false
  $q.notify({ type: 'positive', message: `Организация: ${o.name}` })
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
  } catch {
    $q.notify({ type: 'negative', message: 'Ошибка создания организации' })
  } finally {
    creatingOrg.value = false
  }
}

watch(orgDialog, (val) => { if (val) loadOrgs() })

async function logout() {
  auth.logout()
  await router.push('/login')
}
</script>
