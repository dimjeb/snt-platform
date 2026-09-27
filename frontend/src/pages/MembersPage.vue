<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="text-h6">Члены СНТ</div>
      <q-space />
      <q-btn icon="add" color="green-8" round flat @click="openCreate" />
    </div>

    <q-input v-model="search" outlined dense placeholder="Поиск по ФИО, телефону..." class="q-mb-md" clearable>
      <template #prepend><q-icon name="search" /></template>
    </q-input>

    <q-list separator bordered rounded>
      <q-item v-if="loading">
        <q-item-section class="text-center"><q-spinner color="green-8" /></q-item-section>
      </q-item>

      <q-item v-for="m in members" :key="m.id" clickable v-ripple @click="openDetail(m)">
        <q-item-section avatar>
          <q-avatar color="green-2" text-color="green-9" icon="person" />
        </q-item-section>
        <q-item-section>
          <q-item-label>{{ m.full_name }}</q-item-label>
          <q-item-label caption>
            {{ m.phone || '—' }} · Уч. {{ m.current_plots?.map((p) => p.number).join(', ') || '—' }}
          </q-item-label>
        </q-item-section>
        <q-item-section side>
          <div class="row items-center no-wrap q-gutter-xs">
            <!-- Видно сразу по списку, кому доступ уже выдали, а кому нет:
                 при полутора сотнях человек это иначе ведётся на бумажке. -->
            <q-icon
              :name="accessIcon(m).name" :color="accessIcon(m).color" size="18px"
            >
              <q-tooltip>{{ accessIcon(m).hint }}</q-tooltip>
            </q-icon>
            <q-badge :color="statusColor(m.status)">
              {{ statusLabel(m.status) }}
            </q-badge>
          </div>
        </q-item-section>
      </q-item>

      <q-item v-if="!loading && !members.length">
        <q-item-section class="text-center text-grey-6">Нет членов</q-item-section>
      </q-item>
    </q-list>

    <div class="row justify-center q-mt-md" v-if="totalPages > 1">
      <q-pagination v-model="page" :max="totalPages" :max-pages="5" boundary-numbers @update:model-value="load" />
    </div>

    <!-- Диалог создания/редактирования -->
    <q-dialog v-model="dialog" persistent>
      <q-card style="min-width: 360px; max-width: 480px">
        <q-card-section class="bg-green-8 text-white">
          <div class="text-h6">{{ editMode ? 'Редактировать члена' : 'Добавить члена' }}</div>
        </q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-input
            v-model="form.last_name"
            label="Фамилия *"
            outlined dense
            :rules="[(v) => !!v || 'Обязательно']"
          />
          <q-input v-model="form.first_name" label="Имя *" outlined dense :rules="[(v) => !!v || 'Обязательно']" />
          <q-input v-model="form.patronymic" label="Отчество" outlined dense />
          <q-input v-model="form.phone" label="Телефон" outlined dense />
          <q-input v-model="form.email" label="E-mail" outlined dense type="email" />
          <q-select
            v-model="form.status"
            label="Статус"
            outlined dense
            :options="statusOptions"
            emit-value map-options
          />
          <q-input v-model="form.joined_at" label="Дата вступления" outlined dense type="date" />
          <q-input v-model="form.notes" label="Примечания" outlined dense type="textarea" rows="2" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="green-8" label="Сохранить" :loading="saving" @click="save" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Детали члена -->
    <!-- Пароль показывается ровно один раз: в базе лежит только его хеш,
         повторно показать его нельзя даже председателю. -->
    <q-dialog v-model="passwordDialog" persistent>
      <q-card style="min-width: 320px; max-width: 420px" v-if="issued">
        <q-card-section class="bg-green-8 text-white">
          <div class="text-h6">Доступ выдан</div>
          <div class="text-caption">{{ issued.full_name }}</div>
        </q-card-section>

        <q-card-section class="q-gutter-md">
          <div>
            <div class="text-caption text-grey-7">Логин</div>
            <div class="text-h6 text-weight-bold">{{ issued.username }}</div>
          </div>
          <div>
            <div class="text-caption text-grey-7">Временный пароль</div>
            <div class="text-h5 text-weight-bold access-password">
              {{ issued.password }}
            </div>
          </div>

          <q-banner dense class="bg-orange-1 text-orange-10">
            <template #avatar><q-icon name="warning" color="orange-9" /></template>
            Запишите или скопируйте сейчас. Повторно пароль показать нельзя —
            в базе хранится только его зашифрованный отпечаток. Потеряется —
            останется сбросить.
          </q-banner>

          <div class="text-caption text-grey-7">
            При первом входе система потребует сменить этот пароль на свой.
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat icon="content_copy" label="Скопировать" @click="copyIssued" />
          <q-btn color="green-8" unelevated label="Готово" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="detailDialog">
      <q-card style="min-width: 340px; max-width: 480px" v-if="selected">
        <q-card-section class="bg-green-8 text-white">
          <div class="text-h6">{{ selected.full_name }}</div>
          <div class="text-caption">{{ statusLabel(selected.status) }}</div>
        </q-card-section>
        <q-card-section>
          <q-list dense>
            <q-item v-if="selected.phone">
              <q-item-section side><q-icon name="phone" color="green-8" /></q-item-section>
              <q-item-section>{{ selected.phone }}</q-item-section>
            </q-item>
            <q-item v-if="selected.email">
              <q-item-section side><q-icon name="email" color="green-8" /></q-item-section>
              <q-item-section>{{ selected.email }}</q-item-section>
            </q-item>
            <q-item>
              <q-item-section side><q-icon name="landscape" color="green-8" /></q-item-section>
              <q-item-section>
                Участки: {{ selected.current_plots?.map((p) => p.number).join(', ') || '—' }}
              </q-item-section>
            </q-item>
            <q-item v-if="selected.joined_at">
              <q-item-section side><q-icon name="calendar_today" color="green-8" /></q-item-section>
              <q-item-section>Вступил: {{ selected.joined_at }}</q-item-section>
            </q-item>
            <q-item v-if="selected.notes">
              <q-item-section side><q-icon name="notes" color="grey-6" /></q-item-section>
              <q-item-section class="text-grey-7">{{ selected.notes }}</q-item-section>
            </q-item>
            <q-item>
              <q-item-section side>
                <q-icon :name="accessIcon(selected).name"
                        :color="accessIcon(selected).color" />
              </q-item-section>
              <q-item-section>
                <q-item-label>{{ accessIcon(selected).hint }}</q-item-label>
                <q-item-label caption v-if="selected.account">
                  Логин: {{ selected.account.username }}
                </q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>

        <!-- Выдача доступа — дело председателя: это заведение учётной
             записи с паролем, а не работа с деньгами. -->
        <q-card-section v-if="auth.isChairman" class="q-pt-none">
          <q-btn
            v-if="!selected.account"
            outline color="green-8" icon="key" class="full-width"
            label="Выдать доступ" :loading="accessLoading"
            @click="grantAccess(selected)"
          />
          <q-btn
            v-else
            outline color="orange-8" icon="lock_reset" class="full-width"
            label="Сбросить пароль" :loading="accessLoading"
            @click="confirmReset(selected)"
          />
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="Закрыть" v-close-popup />
          <q-btn flat color="negative" icon="delete" @click="confirmDelete(selected)" />
          <q-btn flat color="green-8" icon="edit" label="Изменить" @click="openEdit(selected)" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Подтверждение удаления -->
    <q-dialog v-model="deleteDialog">
      <q-card>
        <q-card-section>
          <div class="text-h6">Удалить члена?</div>
          <div class="q-mt-sm text-grey-7">{{ selected?.full_name }}</div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn flat color="negative" label="Удалить" :loading="deleting" @click="deleteMember" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import api from 'src/api/client'
import { useAuthStore } from 'stores/auth'

const $q = useQuasar()
const auth = useAuthStore()
const members = ref([])
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const page = ref(1)
const totalPages = ref(1)
const search = ref('')
const dialog = ref(false)
const detailDialog = ref(false)
const deleteDialog = ref(false)
const editMode = ref(false)
const selected = ref(null)
const accessLoading = ref(false)
const passwordDialog = ref(false)
const issued = ref(null)

const emptyForm = () => ({
  last_name: '',
  first_name: '',
  patronymic: '',
  phone: '',
  email: '',
  status: 'active',
  joined_at: '',
  notes: '',
})
const form = ref(emptyForm())

const statusOptions = [
  { label: 'Действующий', value: 'active' },
  { label: 'Выбывший', value: 'inactive' },
  { label: 'Наследник', value: 'heir' },
]
function statusLabel(s) {
  return statusOptions.find((o) => o.value === s)?.label || s
}
function statusColor(s) {
  return s === 'active' ? 'positive' : s === 'heir' ? 'orange-7' : 'grey'
}

// Три состояния доступа, различимые одним взглядом по списку:
// нет учётки / выдана, но человек ещё не входил / он уже пользуется.
function accessIcon(m) {
  if (!m?.account) {
    return { name: 'no_accounts', color: 'grey-5', hint: 'Доступ не выдан' }
  }
  if (m.account.must_change_password) {
    return {
      name: 'key', color: 'orange-8',
      hint: 'Пароль выдан, человек ещё не входил',
    }
  }
  return { name: 'verified_user', color: 'green-7', hint: 'Пользуется кабинетом' }
}

function showIssued(data) {
  issued.value = data
  passwordDialog.value = true
}

async function copyIssued() {
  const text = `Сайт: ${window.location.origin}\n`
    + `Логин: ${issued.value.username}\n`
    + `Пароль: ${issued.value.password}`
  try {
    await navigator.clipboard.writeText(text)
    $q.notify({ type: 'positive', message: 'Скопировано' })
  } catch {
    // В браузере без разрешения на буфер обмена копирование недоступно,
    // и молчать об этом нельзя: человек решит, что скопировалось.
    $q.notify({
      type: 'warning', timeout: 0, multiLine: true,
      actions: [{ label: 'Понятно', color: 'white' }],
      message: 'Браузер не дал доступ к буферу обмена — перепишите пароль вручную.',
    })
  }
}

async function grantAccess(m) {
  accessLoading.value = true
  try {
    const { data } = await api.post(`/members/${m.id}/grant-access/`)
    detailDialog.value = false
    showIssued(data)
    await load()
  } catch (e) {
    $q.notify({
      type: 'negative',
      message: e.response?.data?.detail || 'Не удалось выдать доступ',
    })
  } finally { accessLoading.value = false }
}

function confirmReset(m) {
  $q.dialog({
    title: 'Сбросить пароль?',
    message: `Старый пароль ${m.full_name} перестанет работать сразу. `
      + 'Новый нужно будет передать лично.',
    cancel: 'Отмена',
    ok: { label: 'Сбросить', color: 'orange-8', unelevated: true },
    persistent: true,
  }).onOk(() => resetPassword(m))
}

async function resetPassword(m) {
  accessLoading.value = true
  try {
    const { data } = await api.post(`/members/${m.id}/reset-password/`)
    detailDialog.value = false
    showIssued(data)
    await load()
  } catch (e) {
    $q.notify({
      type: 'negative',
      message: e.response?.data?.detail || 'Не удалось сбросить пароль',
    })
  } finally { accessLoading.value = false }
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/members/', {
      params: { page: page.value, page_size: 20, search: search.value || undefined },
    })
    members.value = data.results
    totalPages.value = Math.ceil((data.count || 0) / 20)
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Ошибка загрузки. Выберите организацию.' })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editMode.value = false
  form.value = emptyForm()
  dialog.value = true
}

function openEdit(m) {
  editMode.value = true
  form.value = {
    id: m.id,
    last_name: m.last_name,
    first_name: m.first_name,
    patronymic: m.patronymic || '',
    phone: m.phone || '',
    email: m.email || '',
    status: m.status,
    joined_at: m.joined_at || '',
    notes: m.notes || '',
  }
  detailDialog.value = false
  dialog.value = true
}

function openDetail(m) {
  selected.value = m
  detailDialog.value = true
}

function confirmDelete(m) {
  selected.value = m
  detailDialog.value = false
  deleteDialog.value = true
}

async function save() {
  if (!form.value.last_name || !form.value.first_name) {
    $q.notify({ type: 'warning', message: 'Заполните фамилию и имя' })
    return
  }
  saving.value = true
  try {
    const payload = { ...form.value }
    delete payload.id
    // DateField в DRF не принимает пустую строку — только null или дату.
    // Добавление члена без даты вступления (обычный случай) падало с 400,
    // а диалог оставался открытым: он закрывается только при успехе.
    if (!payload.joined_at) payload.joined_at = null
    if (editMode.value) {
      await api.patch(`/members/${form.value.id}/`, payload)
    } else {
      await api.post('/members/', payload)
    }
    dialog.value = false
    await load()
    $q.notify({ type: 'positive', message: 'Сохранено' })
  } catch (e) {
    const msg = e.response?.data ? JSON.stringify(e.response.data) : 'Ошибка сохранения'
    $q.notify({ type: 'negative', message: msg })
  } finally {
    saving.value = false
  }
}

async function deleteMember() {
  deleting.value = true
  try {
    await api.delete(`/members/${selected.value.id}/`)
    deleteDialog.value = false
    await load()
    $q.notify({ type: 'positive', message: 'Удалено' })
  } catch {
    $q.notify({ type: 'negative', message: 'Ошибка удаления' })
  } finally {
    deleting.value = false
  }
}

watch(search, () => { page.value = 1; load() }, { debounce: 400 })
onMounted(load)
</script>

<style scoped>
.access-password {
  font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  letter-spacing: 1px;
  user-select: all;
}
</style>
