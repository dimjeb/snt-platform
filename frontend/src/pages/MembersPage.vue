<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="text-h6">Члены СНТ</div>
      <q-space />
      <q-btn icon="add" color="green-8" round flat @click="openCreate" />
    </div>

    <q-input v-model="search" outlined dense placeholder="Поиск по ФИО..." class="q-mb-md" clearable>
      <template #prepend><q-icon name="search" /></template>
    </q-input>

    <q-list separator bordered rounded>
      <q-item v-if="loading"><q-item-section class="text-center"><q-spinner color="green-8" /></q-item-section></q-item>

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
          <q-badge :color="m.status === 'active' ? 'positive' : 'grey'">
            {{ statusLabel(m.status) }}
          </q-badge>
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
      <q-card style="min-width: 340px">
        <q-card-section class="text-h6">{{ editMode ? 'Редактировать' : 'Добавить члена' }}</q-card-section>
        <q-card-section>
          <q-form @submit.prevent="save" class="q-gutter-sm">
            <q-input v-model="form.full_name" label="ФИО *" outlined dense :rules="[(v) => !!v || 'Обязательно']" />
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
          </q-form>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="green-8" label="Сохранить" :loading="saving" @click="save" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Детали члена -->
    <q-dialog v-model="detailDialog">
      <q-card style="min-width: 340px" v-if="selected">
        <q-card-section class="bg-green-8 text-white">
          <div class="text-h6">{{ selected.full_name }}</div>
          <div class="text-caption">{{ statusLabel(selected.status) }}</div>
        </q-card-section>
        <q-card-section>
          <q-list dense>
            <q-item><q-item-section side>📞</q-item-section><q-item-section>{{ selected.phone || '—' }}</q-item-section></q-item>
            <q-item><q-item-section side>✉️</q-item-section><q-item-section>{{ selected.email || '—' }}</q-item-section></q-item>
            <q-item><q-item-section side>🌱</q-item-section><q-item-section>Участки: {{ selected.current_plots?.map((p) => p.number).join(', ') || '—' }}</q-item-section></q-item>
            <q-item><q-item-section side>📅</q-item-section><q-item-section>Вступил: {{ selected.joined_at || '—' }}</q-item-section></q-item>
          </q-list>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Закрыть" v-close-popup />
          <q-btn flat color="green-8" icon="edit" @click="openEdit(selected)" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import api from 'src/api/client'

const $q = useQuasar()
const members = ref([])
const loading = ref(false)
const saving = ref(false)
const page = ref(1)
const totalPages = ref(1)
const search = ref('')
const dialog = ref(false)
const detailDialog = ref(false)
const editMode = ref(false)
const selected = ref(null)

const form = ref({ full_name: '', phone: '', email: '', status: 'active', joined_at: '' })

const statusOptions = [
  { label: 'Активный', value: 'active' },
  { label: 'Неактивный', value: 'inactive' },
  { label: 'Наследник', value: 'heir' },
]
function statusLabel(s) {
  return statusOptions.find((o) => o.value === s)?.label || s
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/members/', {
      params: { page: page.value, page_size: 20, search: search.value || undefined },
    })
    members.value = data.results
    totalPages.value = Math.ceil(data.count / 20)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editMode.value = false
  form.value = { full_name: '', phone: '', email: '', status: 'active', joined_at: '' }
  dialog.value = true
}

function openEdit(m) {
  editMode.value = true
  form.value = { ...m }
  detailDialog.value = false
  dialog.value = true
}

function openDetail(m) {
  selected.value = m
  detailDialog.value = true
}

async function save() {
  saving.value = true
  try {
    if (editMode.value) {
      await api.patch(`/members/${form.value.id}/`, form.value)
    } else {
      await api.post('/members/', form.value)
    }
    dialog.value = false
    await load()
    $q.notify({ type: 'positive', message: 'Сохранено' })
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Ошибка сохранения' })
  } finally {
    saving.value = false
  }
}

watch(search, () => { page.value = 1; load() }, { debounce: 400 })
onMounted(load)
</script>
