<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-mb-md">
      <q-space />
      <q-btn
        icon="upload_file"
        color="primary"
        label="Загрузить"
        unelevated
        @click="uploadDialog = true"
      />
    </div>

    <!-- Разобранная выписка -->
    <q-card flat bordered v-if="statement" class="q-mb-md">
      <q-card-section class="bg-primary text-white">
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
          <div class="text-h6 text-weight-bold text-positive">{{ summary.matched }}</div>
          <div class="text-caption text-grey-7">опознано</div>
        </div>
        <div class="col-4">
          <div class="text-h6 text-weight-bold" :class="summary.pending_unmatched ? 'text-negative' : ''">
            {{ summary.pending_unmatched }}
          </div>
          <div class="text-caption text-grey-7">ждут участка</div>
        </div>
      </q-card-section>

      <q-card-section v-if="summary.pending_unmatched" class="bg-orange-1 text-orange-10 text-body2">
        <q-icon name="warning" class="q-mr-xs" />
        Строки без участка не проводятся. Укажите участок — и проведите выписку
        ещё раз (это можно и после первого проведения), а если поступление не
        взнос (проценты банка, возврат) — нажмите «Пропустить».
      </q-card-section>

      <q-list separator>
        <q-item v-for="t in statement.transactions" :key="t.id">
          <q-item-section avatar>
            <q-icon :name="rowIcon(t).name" :color="rowIcon(t).color">
              <q-tooltip>{{ t.status_display }}</q-tooltip>
            </q-icon>
          </q-item-section>
          <q-item-section>
            <q-item-label>
              {{ t.date }} · {{ formatMoney(t.amount) }} ₽
            </q-item-label>
            <q-item-label caption>{{ t.payer_name }}</q-item-label>
            <q-item-label caption class="text-grey-7">{{ t.purpose }}</q-item-label>
            <!-- На что платили. Сайт угадывает по назначению платежа, а
                 казначей поправляет до проведения: при проведении деньги
                 сначала идут в начисления этой категории. -->
            <q-item-label caption>
              <q-select
                v-if="t.status === 'new'"
                :model-value="t.category"
                :options="categoryOptions"
                emit-value map-options dense borderless
                options-dense
                style="max-width: 220px"
                @update:model-value="(v) => setCategory(t, v)"
              >
                <template #prepend><q-icon name="label" size="16px" /></template>
              </q-select>
              <span v-else-if="t.category" class="text-grey-8">
                {{ t.category_display }}
              </span>
            </q-item-label>
            <q-item-label v-if="t.allocation && t.allocation.length" caption class="text-blue-9">
              Разделено: {{ allocationText(t) }}
            </q-item-label>
            <q-item-label v-if="t.status === 'new'" caption>
              <q-btn flat dense size="sm" color="primary" icon="call_split"
                     :label="t.allocation && t.allocation.length ? 'Изменить разделение' : 'Разделить по категориям'"
                     @click="openSplit(t)" />
              <q-btn flat dense size="sm" color="grey-8" icon="do_not_disturb_on"
                     label="Пропустить" class="q-ml-sm" @click="skipRow(t)" />
            </q-item-label>
            <q-item-label v-else-if="t.status === 'skipped'" caption>
              <q-btn flat dense size="sm" color="primary" icon="undo"
                     label="Вернуть к проведению" @click="unskipRow(t)" />
            </q-item-label>
            <q-item-label caption v-if="t.note"
                          :class="t.status === 'skipped' ? 'text-grey-7' : 'text-orange-9'">
              {{ t.note }}
            </q-item-label>
          </q-item-section>
          <q-item-section side style="min-width: 140px">
            <div v-if="t.status === 'skipped'" class="text-right text-grey-7">пропущена</div>
            <div v-else-if="t.plot_number" class="text-right">
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
        <!-- Кнопка есть, пока есть что проводить, — и у частично
             проведённой выписки тоже: строки, которым участок указали
             после первого проведения, проводятся ею же. -->
        <q-btn
          v-if="statement.status !== 'applied'"
          color="primary"
          icon="done_all"
          :label="`Провести ${summary.pending} ${plural(summary.pending, 'платёж', 'платежа', 'платежей')}`"
          unelevated
          :loading="applying"
          :disable="!summary.pending"
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
      <q-item v-for="s in history" :key="s.id" clickable @click="openFromHistory(s.id)">
        <q-item-section>
          <q-item-label>{{ s.file_name }}</q-item-label>
          <q-item-label caption>
            {{ s.date_from }} — {{ s.date_to }} · строк: {{ s.rows_count }}
          </q-item-label>
        </q-item-section>
        <q-item-section side>
          <q-badge :color="{ applied: 'positive', partial: 'orange-8' }[s.status] || 'grey-7'">
            {{ s.status_display }}
          </q-badge>
        </q-item-section>
      </q-item>
    </q-list>

    <!-- Разделение одного платежа по категориям -->
    <q-dialog v-model="splitDialog" persistent>
      <q-card style="min-width: 340px; max-width: 460px">
        <q-card-section class="text-h6">Разделить по категориям</q-card-section>
        <q-card-section v-if="splitRow" class="q-gutter-sm">
          <div class="text-body2">
            Платёж {{ formatMoney(splitRow.amount) }} ₽ · {{ splitRow.purpose }}
          </div>
          <div v-for="(part, i) in splitParts" :key="i" class="row q-col-gutter-sm items-center">
            <div class="col-6">
              <q-select v-model="part.category" :options="splitCategoryOptions"
                        emit-value map-options outlined dense label="Категория" />
            </div>
            <div class="col-4">
              <q-input v-model="part.amount" outlined dense type="number" label="Сумма" />
            </div>
            <div class="col-2">
              <q-btn flat round dense icon="close" @click="splitParts.splice(i, 1)" />
            </div>
          </div>
          <q-btn v-if="splitParts.length < 3" flat dense size="sm" icon="add"
                 label="Ещё категория" color="primary"
                 @click="addSplitPart" />
          <div class="text-caption"
               :class="splitRest < 0 ? 'text-negative' : 'text-grey-8'">
            <template v-if="splitRest < 0">
              Части больше платежа на {{ formatMoney(-splitRest) }} ₽ — уменьшите.
            </template>
            <template v-else-if="splitRest > 0">
              Не разделено {{ formatMoney(splitRest) }} ₽ — разнесутся как обычно:
              сначала в категорию строки, потом в остальные начисления.
            </template>
            <template v-else>Разделено полностью.</template>
          </div>
          <div class="text-caption text-grey-7">
            Если по категории долга меньше, чем указано, недостающее уйдёт в
            другие начисления — сайт напишет об этом в примечании к строке.
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Убрать разделение" color="grey-8"
                 @click="splitParts = []; saveSplit()" />
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="primary" label="Сохранить" unelevated
                 :disable="splitRest < 0 || !splitPartsValid"
                 @click="saveSplit" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Загрузка -->
    <q-dialog v-model="uploadDialog">
      <q-card style="min-width: 340px; max-width: 460px">
        <q-card-section class="bg-primary text-white">
          <div class="text-h6">Загрузить выписку</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-file
            v-model="file"
            label="Файл выписки"
            outlined
            accept=".txt,.1c,.xlsx"
            :error="!!uploadError"
            :error-message="uploadError"
          >
            <template #prepend><q-icon name="attach_file" /></template>
          </q-file>
          <div class="text-caption text-grey-7">
            Подойдёт либо файл обмена с 1С (<code>kl_to_1c.txt</code> —
            в Сбербанк Бизнес и ВТБ Бизнес это выгрузка «Обмен с 1С»),
            либо обычная выписка по счёту в Excel (<code>.xlsx</code>),
            которую ВТБ Бизнес отдаёт кнопкой «Выписка».
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn
            color="primary"
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
import { computed, onMounted, ref } from 'vue'
import { useQuasar } from 'quasar'
import { useRoute } from 'vue-router'
import api from 'src/api/client'
import { formatMoney } from 'src/utils/money'

const $q = useQuasar()
const route = useRoute()

function plural(n, one, few, many) {
  const a = Math.abs(n) % 100
  if (a >= 11 && a <= 19) return many
  const b = a % 10
  return b === 1 ? one : (b >= 2 && b <= 4 ? few : many)
}

function rowIcon(t) {
  if (t.status === 'applied') return { name: 'check_circle', color: 'positive' }
  if (t.status === 'skipped') return { name: 'do_not_disturb_on', color: 'grey-6' }
  return t.plot_number ? { name: 'account_balance', color: 'primary' } : { name: 'help', color: 'negative' }
}

const statement = ref(null)
const summary = ref({ total_rows: 0, matched: 0, unmatched: 0, pending: 0, pending_unmatched: 0 })
const history = ref([])
const uploadDialog = ref(false)
const file = ref(null)
const uploading = ref(false)
const applying = ref(false)
const uploadError = ref('')
const manualPlot = ref({})
const allPlots = ref([])
const plotOptions = ref([])


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

const categoryOptions = [
  { label: 'Категория не указана', value: '' },
  { label: 'Членский взнос', value: 'membership' },
  { label: 'Целевой взнос', value: 'target' },
  { label: 'Электроэнергия', value: 'electricity' },
]

const splitDialog = ref(false)
const splitRow = ref(null)
const splitParts = ref([])
const splitCategoryOptions = categoryOptions.filter((o) => o.value)
const categoryNames = Object.fromEntries(splitCategoryOptions.map((o) => [o.value, o.label]))

function allocationText(row) {
  return row.allocation
    .map((p) => `${categoryNames[p.category] || p.category} ${formatMoney(p.amount)} ₽`)
    .join(' + ')
}

const splitRest = computed(() => {
  if (!splitRow.value) return 0
  const used = splitParts.value.reduce((sum, p) => sum + (Number(p.amount) || 0), 0)
  return Math.round((Number(splitRow.value.amount) - used) * 100) / 100
})

const splitPartsValid = computed(() => splitParts.value.every(
  (p) => p.category && Number(p.amount) > 0,
) && new Set(splitParts.value.map((p) => p.category)).size === splitParts.value.length)

// По умолчанию — то, что распознано из назначения платежа, на всю сумму.
// Казначею остаётся уменьшить её и добавить вторую категорию, а не
// заполнять всё с нуля.
function openSplit(row) {
  splitRow.value = row
  splitParts.value = (row.allocation && row.allocation.length)
    ? row.allocation.map((p) => ({ ...p }))
    : [{ category: row.category || null, amount: String(row.amount) }]
  splitDialog.value = true
}

// Новая строка: следующая ещё не выбранная категория и неразделённый
// остаток. В обычном случае «членский + целевой» руками вводится одно
// число — сумма первой части.
function addSplitPart() {
  const used = new Set(splitParts.value.map((p) => p.category))
  const next = splitCategoryOptions.find((o) => !used.has(o.value))
  splitParts.value.push({
    category: next ? next.value : null,
    amount: splitRest.value > 0 ? String(splitRest.value) : '',
  })
}

async function saveSplit() {
  try {
    const { data } = await api.patch(`/billing/transactions/${splitRow.value.id}/`,
      { allocation: splitParts.value })
    splitRow.value.allocation = data.allocation
    splitDialog.value = false
  } catch (e) {
    const d = e?.response?.data
    const msg = d?.allocation?.[0] || d?.detail || d?.non_field_errors?.[0]
      || 'Не удалось сохранить разделение'
    $q.notify({ type: 'negative', message: msg })
  }
}

async function setCategory(transaction, category) {
  try {
    await api.patch(`/billing/transactions/${transaction.id}/`, { category })
    transaction.category = category
  } catch (e) {
    $q.notify({ type: 'negative', message: 'Не удалось сохранить категорию' })
  }
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
        (data.skipped ? `. Ждут участка: ${data.skipped}` : ''),
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

// Выписка открывается над списком — на длинной странице её не видно.
async function openFromHistory(id) {
  await openStatement(id)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function skipRow(t) {
  $q.dialog({
    title: 'Пропустить строку',
    message: 'Деньги никуда не разнесутся, строка перестанет ждать проведения. '
      + 'Почему пропускаем? (необязательно)',
    prompt: { model: '', type: 'text', placeholder: 'например: проценты банка' },
    cancel: { flat: true, label: 'Отмена' },
    ok: { unelevated: true, color: 'primary', label: 'Пропустить' },
  }).onOk(async (reason) => {
    try {
      await api.post(`/billing/transactions/${t.id}/skip/`, { reason })
      await openStatement(statement.value.id)
      await loadHistory()
    } catch (e) {
      $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Не удалось пропустить строку' })
    }
  })
}

async function unskipRow(t) {
  try {
    await api.post(`/billing/transactions/${t.id}/unskip/`)
    await openStatement(statement.value.id)
    await loadHistory()
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Не удалось вернуть строку' })
  }
}

onMounted(async () => {
  await loadHistory()
  // Ссылка с главной («Провести выписку») открывает сразу нужную выписку.
  const id = Number(route.query.open)
  if (id) {
    try {
      await openStatement(id)
    } catch { /* выписку удалили — остаёмся на списке */ }
  }
})
</script>
