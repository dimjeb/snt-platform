<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <div class="text-h6">Банковская выписка</div>
      <q-space />
      <q-btn
        icon="upload_file"
        color="green-8"
        label="Загрузить"
        unelevated
        @click="uploadDialog = true"
      />
    </div>

    <!-- Разобранная выписка -->
    <q-card flat bordered v-if="statement" class="q-mb-md">
      <q-card-section class="bg-green-8 text-white">
        <div class="text-subtitle1">{{ statement.file_name }}</div>
        <div class="text-caption">
          {{ statement.date_from }} — {{ statement.date_to }} · счёт {{ statement.account }}
        </div>
      </q-card-section>

      <q-card-section class="row q-col-gutter-sm text-center">
        <div class="col-4">
          <div class="text-h6 text-weight-bold">{{ summary.total_rows }}</div>
          <div class="text-caption text-grey-7">поступлений</div>
        </div>
        <div class="col-4">
          <div class="text-h6 text-weight-bold text-green-8">{{ summary.matched }}</div>
          <div class="text-caption text-grey-7">опознано</div>
        </div>
        <div class="col-4">
          <div class="text-h6 text-weight-bold" :class="summary.unmatched ? 'text-negative' : ''">
            {{ summary.unmatched }}
          </div>
          <div class="text-caption text-grey-7">без участка</div>
        </div>
      </q-card-section>

      <q-card-section v-if="summary.unmatched" class="bg-orange-1 text-orange-10 text-body2">
        <q-icon name="warning" class="q-mr-xs" />
        Строки без участка не будут проведены. Укажите участок вручную или
        оставьте — их можно провести позже.
      </q-card-section>

      <q-list separator>
        <q-item v-for="t in statement.transactions" :key="t.id">
          <q-item-section avatar>
            <q-icon
              :name="t.status === 'applied' ? 'check_circle'
                    : t.plot_number ? 'account_balance' : 'help'"
              :color="t.status === 'applied' ? 'positive'
                     : t.plot_number ? 'green-8' : 'negative'"
            />
          </q-item-section>
          <q-item-section>
            <q-item-label>
              {{ t.date }} · {{ formatMoney(t.amount) }} ₽
            </q-item-label>
            <q-item-label caption>{{ t.payer_name }}</q-item-label>
            <q-item-label caption class="text-grey-7">{{ t.purpose }}</q-item-label>
            <q-item-label caption v-if="t.note" class="text-orange-9">
              {{ t.note }}
            </q-item-label>
          </q-item-section>
          <q-item-section side style="min-width: 140px">
            <div v-if="t.plot_number" class="text-right">
              <div class="text-weight-medium">уч. {{ t.plot_number }}</div>
              <div class="text-caption text-grey-6">{{ matchLabel(t) }}</div>
            </div>
            <q-select
              v-else
              v-model="manualPlot[t.id]"
              :options="plotOptions"
              option-value="id"
              option-label="number"
              emit-value
              map-options
              dense
              outlined
              use-input
              label="участок"
              @filter="filterPlots"
              @update:model-value="(v) => assignPlot(t, v)"
            />
          </q-item-section>
        </q-item>
      </q-list>

      <q-card-actions align="right" class="q-pa-md">
        <q-btn
          v-if="statement.status !== 'applied'"
          color="green-8"
          icon="done_all"
          :label="`Провести ${summary.matched} платежей`"
          unelevated
          :loading="applying"
          :disable="!summary.matched"
          @click="applyStatement"
        />
        <div v-else class="text-positive">
          <q-icon name="check_circle" /> Выписка проведена
        </div>
      </q-card-actions>
    </q-card>

    <!-- История -->
    <div class="text-subtitle2 q-mb-sm" v-if="history.length">Загруженные ранее</div>
    <q-list separator bordered rounded v-if="history.length">
      <q-item v-for="s in history" :key="s.id" clickable @click="openStatement(s.id)">
        <q-item-section>
          <q-item-label>{{ s.file_name }}</q-item-label>
          <q-item-label caption>
            {{ s.date_from }} — {{ s.date_to }} · строк: {{ s.rows_count }}
          </q-item-label>
        </q-item-section>
        <q-item-section side>
          <q-badge :color="s.status === 'applied' ? 'positive' : 'orange-8'">
            {{ s.status_display }}
          </q-badge>
        </q-item-section>
      </q-item>
    </q-list>

    <!-- Загрузка -->
    <q-dialog v-model="uploadDialog">
      <q-card style="min-width: 340px; max-width: 460px">
        <q-card-section class="bg-green-8 text-white">
          <div class="text-h6">Загрузить выписку</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-file
            v-model="file"
            label="Файл выписки"
            outlined
            accept=".txt,.1c"
            :error="!!uploadError"
            :error-message="uploadError"
          >
            <template #prepend><q-icon name="attach_file" /></template>
          </q-file>
          <div class="text-caption text-grey-7">
            Нужен файл обмена с 1С из банк-клиента — обычно называется
            <code>kl_to_1c.txt</code>. В Сбербанк Бизнес и ВТБ Бизнес это
            выгрузка «Обмен с 1С» за нужный период.
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn
            color="green-8"
            label="Разобрать"
            unelevated
            :loading="uploading"
            :disable="!file"
            @click="upload"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useQuasar } from 'quasar'
import api from 'src/api/client'

const $q = useQuasar()

const statement = ref(null)
const summary = ref({ total_rows: 0, matched: 0, unmatched: 0 })
const history = ref([])
const uploadDialog = ref(false)
const file = ref(null)
const uploading = ref(false)
const applying = ref(false)
const uploadError = ref('')
const manualPlot = ref({})
const allPlots = ref([])
const plotOptions = ref([])

function formatMoney(v) {
  return Number(v).toLocaleString('ru-RU', { minimumFractionDigits: 2 })
}

function matchLabel(t) {
  return {
    plot: 'по назначению',
    name: 'по ФИО',
    manual: 'вручную',
  }[t.match_kind] || ''
}

async function loadHistory() {
  try {
    const { data } = await api.get('/billing/statements/')
    history.value = data.results || data
  } catch { /* список не критичен */ }
}

async function loadPlots() {
  if (allPlots.value.length) return
  const { data } = await api.get('/plots/?page_size=500')
  allPlots.value = data.results || data
  plotOptions.value = allPlots.value
}

function filterPlots(val, update) {
  loadPlots().then(() => {
    update(() => {
      const q = (val || '').toLowerCase()
      plotOptions.value = q
        ? allPlots.value.filter((p) => String(p.number).toLowerCase().includes(q))
        : allPlots.value
    })
  })
}

async function upload() {
  uploading.value = true
  uploadError.value = ''
  try {
    const form = new FormData()
    form.append('file', file.value)
    const { data } = await api.post('/billing/statements/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    statement.value = data
    summary.value = data.summary
    uploadDialog.value = false
    file.value = null
    const s = data.stats
    $q.notify({
      type: 'positive',
      message: `Загружено ${s.loaded} поступлений` +
        (s.duplicates ? `, пропущено дублей: ${s.duplicates}` : ''),
    })
    await loadHistory()
    await loadPlots()
  } catch (e) {
    uploadError.value = e.response?.data?.detail || 'Не удалось разобрать файл'
  } finally {
    uploading.value = false
  }
}

async function openStatement(id) {
  const { data } = await api.get(`/billing/statements/${id}/`)
  statement.value = data
  const s = await api.get(`/billing/statements/${id}/summary/`)
  summary.value = s.data
  await loadPlots()
}

async function assignPlot(transaction, plotId) {
  if (!plotId) return
  try {
    await api.patch(`/billing/transactions/${transaction.id}/`, { plot: plotId })
    await openStatement(statement.value.id)
    $q.notify({ type: 'positive', message: 'Участок указан' })
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Не удалось указать участок' })
  }
}

async function applyStatement() {
  applying.value = true
  try {
    const { data } = await api.post(`/billing/statements/${statement.value.id}/apply/`)
    statement.value = data.statement
    await openStatement(statement.value.id)
    $q.notify({
      type: 'positive',
      message: `Проведено ${data.applied} платежей на ${formatMoney(data.total)} ₽` +
        (data.skipped ? `, пропущено без участка: ${data.skipped}` : ''),
    })
    await loadHistory()
  } catch (e) {
    $q.notify({
      type: 'negative',
      message: e.response?.data?.detail || 'Не удалось провести выписку',
    })
  } finally {
    applying.value = false
  }
}

onMounted(loadHistory)
</script>
