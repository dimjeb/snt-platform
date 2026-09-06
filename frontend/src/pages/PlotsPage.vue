<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="text-h6">Участки</div>
      <q-space />
      <q-btn icon="add" color="green-8" round flat @click="openCreate" />
    </div>

    <q-list separator bordered rounded>
      <q-item v-if="loading"><q-item-section class="text-center"><q-spinner color="green-8" /></q-item-section></q-item>

      <q-item v-for="p in plots" :key="p.id" clickable v-ripple @click="openDetail(p)">
        <q-item-section avatar>
          <q-avatar color="blue-2" text-color="blue-9">{{ p.number }}</q-avatar>
        </q-item-section>
        <q-item-section>
          <q-item-label>Участок №{{ p.number }}</q-item-label>
          <q-item-label caption>
            {{ p.area_sotok }} сот. · {{ p.current_owner?.full_name || 'Без владельца' }}
          </q-item-label>
        </q-item-section>
        <q-item-section side v-if="p.cadastral_number">
          <q-icon name="info" color="grey-5" size="xs" />
        </q-item-section>
      </q-item>

      <q-item v-if="!loading && !plots.length">
        <q-item-section class="text-center text-grey-6">Нет участков</q-item-section>
      </q-item>
    </q-list>

    <div class="row justify-center q-mt-md" v-if="totalPages > 1">
      <q-pagination v-model="page" :max="totalPages" :max-pages="5" boundary-numbers @update:model-value="load" />
    </div>

    <!-- Создание участка -->
    <q-dialog v-model="dialog" persistent>
      <q-card style="min-width: 320px">
        <q-card-section class="text-h6">{{ editMode ? 'Редактировать' : 'Новый участок' }}</q-card-section>
        <q-card-section>
          <q-form class="q-gutter-sm">
            <q-input v-model="form.number" label="Номер участка *" outlined dense type="number" />
            <q-input v-model="form.area_sotok" label="Площадь (соток)" outlined dense type="number" step="0.01" />
            <q-input v-model="form.cadastral_number" label="Кадастровый номер" outlined dense />
          </q-form>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="green-8" label="Сохранить" :loading="saving" @click="save" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Детали -->
    <q-dialog v-model="detailDialog">
      <q-card style="min-width: 320px" v-if="selected">
        <q-card-section class="bg-blue-8 text-white">
          <div class="text-h6">Участок №{{ selected.number }}</div>
          <div class="text-caption">{{ selected.area_sotok }} соток</div>
        </q-card-section>
        <q-card-section>
          <q-list dense>
            <q-item>
              <q-item-section side>👤</q-item-section>
              <q-item-section>Владелец: {{ selected.current_owner?.full_name || 'Не указан' }}</q-item-section>
            </q-item>
            <q-item v-if="selected.cadastral_number">
              <q-item-section side>📋</q-item-section>
              <q-item-section>Кадастр: {{ selected.cadastral_number }}</q-item-section>
            </q-item>
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
import { ref, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import api from 'src/api/client'

const $q = useQuasar()
const plots = ref([])
const loading = ref(false)
const saving = ref(false)
const page = ref(1)
const totalPages = ref(1)
const dialog = ref(false)
const detailDialog = ref(false)
const editMode = ref(false)
const selected = ref(null)
const form = ref({ number: '', area_sotok: '', cadastral_number: '' })

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/plots/', { params: { page: page.value, page_size: 20 } })
    plots.value = data.results
    totalPages.value = Math.ceil(data.count / 20)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editMode.value = false
  form.value = { number: '', area_sotok: '', cadastral_number: '' }
  dialog.value = true
}
function openEdit(p) {
  editMode.value = true
  form.value = { ...p }
  detailDialog.value = false
  dialog.value = true
}
function openDetail(p) {
  selected.value = p
  detailDialog.value = true
}

async function save() {
  saving.value = true
  try {
    if (editMode.value) {
      await api.patch(`/plots/${form.value.id}/`, form.value)
    } else {
      await api.post('/plots/', form.value)
    }
    dialog.value = false
    await load()
    $q.notify({ type: 'positive', message: 'Сохранено' })
  } catch {
    $q.notify({ type: 'negative', message: 'Ошибка сохранения' })
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
