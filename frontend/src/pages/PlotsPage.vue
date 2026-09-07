<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="text-h6">Участки</div>
      <q-space />
      <q-btn icon="add" color="green-8" round flat @click="openCreate" />
    </div>

    <q-input v-model="search" outlined dense placeholder="Поиск по номеру, кадастру..." class="q-mb-md" clearable>
      <template #prepend><q-icon name="search" /></template>
    </q-input>

    <q-list separator bordered rounded>
      <q-item v-if="loading">
        <q-item-section class="text-center"><q-spinner color="green-8" /></q-item-section>
      </q-item>

      <q-item v-for="p in plots" :key="p.id" clickable v-ripple @click="openDetail(p)">
        <q-item-section avatar>
          <q-avatar color="blue-2" text-color="blue-9" size="42px" font-size="14px">
            {{ p.number }}
          </q-avatar>
        </q-item-section>
        <q-item-section>
          <q-item-label>Участок №{{ p.number }}</q-item-label>
          <q-item-label caption>
            {{ p.area_sotok ? p.area_sotok + ' сот.' : '—' }} ·
            {{ p.current_owner?.full_name || 'Без владельца' }}
          </q-item-label>
        </q-item-section>
        <q-item-section side v-if="p.cadastral_number">
          <q-tooltip>{{ p.cadastral_number }}</q-tooltip>
          <q-icon name="article" color="grey-5" size="xs" />
        </q-item-section>
      </q-item>

      <q-item v-if="!loading && !plots.length">
        <q-item-section class="text-center text-grey-6">Нет участков</q-item-section>
      </q-item>
    </q-list>

    <div class="row justify-center q-mt-md" v-if="totalPages > 1">
      <q-pagination v-model="page" :max="totalPages" :max-pages="5" boundary-numbers @update:model-value="load" />
    </div>

    <!-- Диалог создания/редактирования -->
    <q-dialog v-model="dialog" persistent>
      <q-card style="min-width: 360px; max-width: 480px">
        <q-card-section class="bg-blue-8 text-white">
          <div class="text-h6">{{ editMode ? 'Редактировать участок' : 'Новый участок' }}</div>
        </q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-input
            v-model="form.number"
            label="Номер участка *"
            outlined dense
            :rules="[(v) => !!v || 'Обязательно']"
          />
          <q-input
            v-model="form.area_sotok"
            label="Площадь (соток)"
            outlined dense
            type="number"
            step="0.01"
          />
          <q-input
            v-model="form.cadastral_number"
            label="Кадастровый номер"
            outlined dense
          />
          <q-input
            v-model="form.notes"
            label="Примечания"
            outlined dense
            type="textarea"
            rows="2"
          />

          <!-- Выбор владельца из реестра членов -->
          <q-select
            v-model="form.owner"
            label="Владелец"
            outlined dense
            clearable
            use-input
            input-debounce="300"
            :options="memberOptions"
            option-value="id"
            option-label="full_name"
            emit-value
            map-options
            @filter="filterMembers"
            @clear="form.owner = null"
          >
            <template #prepend><q-icon name="person" color="green-8" /></template>
            <template #no-option>
              <q-item>
                <q-item-section class="text-grey-6">Членов не найдено</q-item-section>
              </q-item>
            </template>
            <template #option="scope">
              <q-item v-bind="scope.itemProps">
                <q-item-section avatar>
                  <q-icon name="person" color="green-8" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>{{ scope.opt.full_name }}</q-item-label>
                  <q-item-label caption v-if="scope.opt.status !== 'active'">
                    {{ statusLabel(scope.opt.status) }}
                  </q-item-label>
                </q-item-section>
              </q-item>
            </template>
          </q-select>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="blue-8" label="Сохранить" :loading="saving" @click="save" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Детали участка -->
    <q-dialog v-model="detailDialog">
      <q-card style="min-width: 340px; max-width: 480px" v-if="selected">
        <q-card-section class="bg-blue-8 text-white">
          <div class="text-h6">Участок №{{ selected.number }}</div>
          <div class="text-caption">{{ selected.area_sotok ? selected.area_sotok + ' соток' : '' }}</div>
        </q-card-section>
        <q-card-section>
          <q-list dense>
            <q-item>
              <q-item-section side><q-icon name="person" color="blue-8" /></q-item-section>
              <q-item-section>
                <q-item-label overline>Владелец</q-item-label>
                <q-item-label>{{ selected.current_owner?.full_name || 'Не назначен' }}</q-item-label>
              </q-item-section>
            </q-item>
            <q-item v-if="selected.cadastral_number">
              <q-item-section side><q-icon name="article" color="blue-8" /></q-item-section>
              <q-item-section>
                <q-item-label overline>Кадастровый номер</q-item-label>
                <q-item-label>{{ selected.cadastral_number }}</q-item-label>
              </q-item-section>
            </q-item>
            <q-item v-if="selected.notes">
              <q-item-section side><q-icon name="notes" color="grey-6" /></q-item-section>
              <q-item-section class="text-grey-7">{{ selected.notes }}</q-item-section>
            </q-item>
          </q-list>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Закрыть" v-close-popup />
          <q-btn flat color="negative" icon="delete" @click="confirmDelete(selected)" />
          <q-btn flat color="blue-8" icon="edit" label="Изменить" @click="openEdit(selected)" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Подтверждение удаления -->
    <q-dialog v-model="deleteDialog">
      <q-card>
        <q-card-section>
          <div class="text-h6">Удалить участок?</div>
          <div class="q-mt-sm text-grey-7">Участок №{{ selected?.number }}</div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn flat color="negative" label="Удалить" :loading="deleting" @click="deletePlot" />
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
const plots = ref([])
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

// Члены для select
const membersAll = ref([])      // полный кеш
const memberOptions = ref([])   // отфильтрованные для select

const emptyForm = () => ({
  number: '',
  area_sotok: '',
  cadastral_number: '',
  notes: '',
  owner: null,   // id владельца (или null)
})
const form = ref(emptyForm())

const statusLabel = (s) => ({ active: 'Действующий', inactive: 'Выбывший', heir: 'Наследник' }[s] || s)

async function loadMembers() {
  if (membersAll.value.length) return  // уже загружены
  try {
    const { data } = await api.get('/members/short/')
    membersAll.value = data
    memberOptions.value = data
  } catch {
    // не критично — select просто будет пустым
  }
}

function filterMembers(val, update) {
  update(() => {
    const q = val.toLowerCase()
    memberOptions.value = q
      ? membersAll.value.filter((m) => m.full_name.toLowerCase().includes(q))
      : membersAll.value
  })
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/plots/', {
      params: { page: page.value, page_size: 20, search: search.value || undefined },
    })
    plots.value = data.results
    totalPages.value = Math.ceil((data.count || 0) / 20)
  } catch {
    $q.notify({ type: 'negative', message: 'Ошибка загрузки. Выберите организацию.' })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editMode.value = false
  form.value = emptyForm()
  loadMembers()
  dialog.value = true
}

function openEdit(p) {
  editMode.value = true
  form.value = {
    id: p.id,
    number: p.number,
    area_sotok: p.area_sotok || '',
    cadastral_number: p.cadastral_number || '',
    notes: p.notes || '',
    owner: p.current_owner?.id ?? null,
  }
  loadMembers()
  detailDialog.value = false
  dialog.value = true
}

function openDetail(p) {
  selected.value = p
  detailDialog.value = true
}

function confirmDelete(p) {
  selected.value = p
  detailDialog.value = false
  deleteDialog.value = true
}

async function save() {
  if (!form.value.number) {
    $q.notify({ type: 'warning', message: 'Укажите номер участка' })
    return
  }
  saving.value = true
  try {
    const payload = {
      number: form.value.number,
      area_sotok: form.value.area_sotok || null,
      cadastral_number: form.value.cadastral_number,
      notes: form.value.notes,
      current_owner_id: form.value.owner,  // null или id члена
    }
    if (editMode.value) {
      await api.patch(`/plots/${form.value.id}/`, payload)
    } else {
      await api.post('/plots/', payload)
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

async function deletePlot() {
  deleting.value = true
  try {
    await api.delete(`/plots/${selected.value.id}/`)
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
