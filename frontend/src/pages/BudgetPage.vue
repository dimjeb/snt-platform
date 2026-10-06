<template>
  <q-page class="q-pa-md">
    <div class="row items-center q-gutter-sm q-mb-md">
      <div class="text-h6">Смета и расходы</div>
      <q-space />
      <q-select v-model="year" :options="yearOptions" dense outlined emit-value map-options
                label="Год" style="min-width:120px" @update:model-value="loadBudget" />
      <q-btn outline color="green-8" icon="add" label="Новая смета" @click="openNewBudget" />
    </div>

    <q-tabs v-model="tab" dense align="left" active-color="green-8" indicator-color="green-8"
            class="q-mb-md" no-caps>
      <q-tab name="budget" label="Смета" />
      <q-tab name="expenses" label="Расходы" />
      <q-tab name="execution" label="Исполнение" />
      <q-tab name="accounting" label="Для бухгалтера" />
    </q-tabs>

    <q-tab-panels v-model="tab" animated>
      <!-- Смета -->
      <q-tab-panel name="budget" class="q-pa-none">
        <div v-if="!budget" class="text-grey-7 q-pa-md">
          Сметы на {{ year }} год ещё нет. Нажмите «Новая смета» — можно взять за основу прошлогоднюю.
        </div>
        <template v-else>
          <div class="row items-center q-gutter-sm q-mb-sm">
            <q-chip :color="budget.status === 'approved' ? 'green-2' : 'orange-2'"
                    :text-color="budget.status === 'approved' ? 'green-10' : 'orange-10'" dense>
              {{ budget.status === 'approved'
                ? `Утверждена ${fmtDate(budget.approved_at)}${budget.protocol_number ? ', протокол № ' + budget.protocol_number : ''}`
                : 'Черновик' }}
            </q-chip>
            <q-select v-model="budget.basis" :options="basisOptions" emit-value map-options dense outlined
                      label="Членский взнос делится" style="min-width:230px"
                      :disable="approved" @update:model-value="saveBasis" />
            <q-space />
            <q-btn flat no-caps color="primary" icon="download" label="Смета" @click="download(`/budgets/${budget.id}/document/smeta/`, `Смета ${year}.xlsx`)" />
            <q-btn flat no-caps color="primary" icon="download" label="Обоснование (ФЭО)" @click="download(`/budgets/${budget.id}/document/feo/`, `ФЭО взносов ${year}.xlsx`)" />
          </div>

          <q-card flat bordered class="q-mb-md">
            <q-card-section class="row q-col-gutter-md">
              <div class="col-12 col-sm-3">
                <div class="text-caption text-grey-7">Расходы за счёт членских</div>
                <div class="text-h6">{{ money(calc.membership_total) }}</div>
              </div>
              <div class="col-12 col-sm-3">
                <div class="text-caption text-grey-7">База</div>
                <div class="text-h6">
                  {{ budget.basis === 'per_sotka' ? `${calc.area} сот.` : `${calc.plots} уч.` }}
                </div>
              </div>
              <div class="col-12 col-sm-3">
                <div class="text-caption text-grey-7">Членский взнос</div>
                <div class="text-h6 text-green-9" data-test="rate">
                  {{ calc.rate ? money(calc.rate) : '—' }}
                  <span class="text-caption">{{ budget.basis === 'per_sotka' ? 'за сотку' : 'с участка' }}</span>
                </div>
              </div>
              <div class="col-12 col-sm-3">
                <div class="text-caption text-grey-7">Соберётся</div>
                <div class="text-h6">{{ calc.collected ? money(calc.collected) : '—' }}</div>
                <div v-if="Number(calc.rounding_surplus) > 0" class="text-caption text-grey-7">
                  +{{ money(calc.rounding_surplus) }} за счёт округления вверх
                </div>
              </div>
            </q-card-section>
            <q-card-section v-if="calc.targets?.length" class="q-pt-none text-body2">
              <span class="text-grey-7">Целевые с участка:</span>
              <span v-for="t in calc.targets" :key="t.id" class="q-ml-sm">«{{ t.name }}» — {{ money(t.per_plot) }}</span>
            </q-card-section>
            <q-card-section v-for="w in calc.warnings" :key="w" class="q-pt-none text-orange-9 text-body2">
              <q-icon name="warning" /> {{ w }}
            </q-card-section>
            <q-card-actions>
              <q-btn v-if="!approved && auth.isChairman" color="green-8" icon="gavel" label="Утвердить (по решению собрания)" @click="approveDialog = true" />
              <q-btn v-if="approved && auth.isChairman" flat color="grey-8" icon="undo" label="Вернуть в черновик" @click="unapprove" />
              <q-btn v-if="approved" outline color="green-8" icon="playlist_add" label="Начислить членский взнос по смете" @click="chargeDialog = true" />
              <q-space />
              <q-btn v-if="!approved" flat color="negative" icon="delete" label="Удалить смету" @click="deleteBudget" />
            </q-card-actions>
          </q-card>

          <div v-for="sec in sections" :key="sec.value" class="q-mb-md">
            <div class="row items-center q-mb-xs">
              <div class="text-subtitle1">{{ sec.label }}</div>
              <q-space />
              <q-btn v-if="!approved" flat dense no-caps color="green-8" icon="add" label="Статья" @click="openItem(null, sec.value)" />
            </div>
            <q-markup-table flat bordered dense separator="cell">
              <thead>
                <tr><th class="text-left">Статья</th><th class="text-left">Расчёт</th>
                  <th class="text-right">Сумма</th><th class="text-left">Обоснование</th><th v-if="!approved"></th></tr>
              </thead>
              <tbody>
                <tr v-for="i in itemsOf(sec.value)" :key="i.id">
                  <td>{{ i.name }}</td>
                  <td>{{ calcText(i) }}</td>
                  <td class="text-right">{{ money(i.amount) }}</td>
                  <td class="text-caption">{{ i.justification }}</td>
                  <td v-if="!approved" class="text-right" style="white-space:nowrap">
                    <q-btn flat dense round size="sm" icon="edit" @click="openItem(i)" />
                    <q-btn flat dense round size="sm" icon="delete" color="negative" @click="deleteItem(i)" />
                  </td>
                </tr>
                <tr v-if="!itemsOf(sec.value).length"><td colspan="5" class="text-grey-6">Статей нет</td></tr>
              </tbody>
            </q-markup-table>
          </div>
        </template>
      </q-tab-panel>

      <!-- Расходы -->
      <q-tab-panel name="expenses" class="q-pa-none">
        <div class="row q-mb-sm">
          <q-btn color="green-8" icon="add" label="Добавить расход" @click="openExpense" />
        </div>
        <q-markup-table flat bordered dense>
          <thead><tr><th class="text-left">Дата</th><th class="text-right">Сумма</th><th class="text-left">Статья</th>
            <th class="text-left">Кому</th><th class="text-left">Документ</th><th class="text-left">Описание</th><th></th></tr></thead>
          <tbody>
            <tr v-for="e in expenses" :key="e.id">
              <td>{{ fmtDate(e.date) }}</td><td class="text-right">{{ money(e.amount) }}</td>
              <td>{{ e.item_name || 'вне сметы' }}</td><td>{{ e.counterparty }}</td>
              <td>{{ e.document }}</td><td>{{ e.description }}</td>
              <td><q-btn flat dense round size="sm" icon="delete" color="negative" @click="deleteExpense(e)" /></td>
            </tr>
            <tr v-if="!expenses.length"><td colspan="7" class="text-grey-6">Расходов за {{ year }} год нет</td></tr>
          </tbody>
        </q-markup-table>
      </q-tab-panel>

      <!-- Исполнение -->
      <q-tab-panel name="execution" class="q-pa-none">
        <div class="row q-gutter-sm q-mb-sm">
          <q-btn v-if="budget" outline color="primary" icon="download" label="Отчёт об исполнении сметы"
                 @click="download(`/budgets/${budget.id}/document/execution/`, `Исполнение сметы ${year}.xlsx`)" />
          <q-btn outline color="primary" icon="download" label="Ведомость для ревизионной комиссии"
                 @click="download(`/reports/revision/?year=${year}`, `Ведомость расчётов ${year}.xlsx`)" />
        </div>
        <template v-if="exec">
          <div class="text-subtitle1">Доходы</div>
          <q-markup-table flat bordered dense class="q-mb-md">
            <thead><tr><th class="text-left">Источник</th><th class="text-right">Начислено</th><th class="text-right">Поступило</th><th class="text-right">Долг</th></tr></thead>
            <tbody>
              <tr v-for="r in exec.income" :key="r.category">
                <td>{{ r.name }}</td><td class="text-right">{{ money(r.charged) }}</td>
                <td class="text-right">{{ money(r.paid) }}</td><td class="text-right">{{ money(r.debt) }}</td>
              </tr>
            </tbody>
          </q-markup-table>
          <div class="text-subtitle1">Расходы</div>
          <q-markup-table flat bordered dense>
            <thead><tr><th class="text-left">Статья</th><th class="text-right">План</th><th class="text-right">Факт</th><th class="text-right">Остаток</th><th class="text-right">%</th></tr></thead>
            <tbody>
              <tr v-for="r in exec.rows" :key="r.id">
                <td>{{ r.name }}</td><td class="text-right">{{ money(r.plan) }}</td>
                <td class="text-right">{{ money(r.fact) }}</td>
                <td class="text-right" :class="Number(r.diff) < 0 ? 'text-negative' : ''">{{ money(r.diff) }}</td>
                <td class="text-right">{{ r.percent ?? '—' }}</td>
              </tr>
              <tr v-if="Number(exec.outside_budget)"><td>Вне статей сметы</td><td></td><td class="text-right">{{ money(exec.outside_budget) }}</td><td></td><td></td></tr>
              <tr class="text-weight-bold"><td>Итого</td><td class="text-right">{{ money(exec.plan_total) }}</td>
                <td class="text-right">{{ money(Number(exec.fact_total) + Number(exec.outside_budget)) }}</td><td></td><td></td></tr>
            </tbody>
          </q-markup-table>
        </template>
        <div v-else class="text-grey-7">Сметы на {{ year }} год нет — сравнивать не с чем.</div>
      </q-tab-panel>

      <!-- Для бухгалтера -->
      <q-tab-panel name="accounting" class="q-pa-none">
        <div class="text-body2 q-mb-sm" style="max-width:720px">
          Файл Excel для бухгалтера за период, по листам: <b>Поступления</b> (только живые деньги — выписка и касса;
          зачёт аванса и переносы не входят, иначе доход задвоится), <b>Начисления</b>, <b>Расходы</b>,
          <b>Сальдо по участкам</b> (долг на начало и конец, аванс).
        </div>
        <div class="row q-gutter-sm items-center">
          <q-input v-model="accFrom" type="date" label="С" outlined dense />
          <q-input v-model="accTo" type="date" label="По" outlined dense />
          <q-btn color="green-8" icon="download" label="Скачать выгрузку"
                 @click="download(`/reports/accounting/?date_from=${accFrom}&date_to=${accTo}`, `Для бухгалтера ${accFrom}—${accTo}.xlsx`)" />
        </div>
      </q-tab-panel>
    </q-tab-panels>

    <!-- Новая смета -->
    <q-dialog v-model="newDialog">
      <q-card style="min-width:320px">
        <q-card-section class="text-h6">Новая смета</q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-input v-model.number="newForm.year" type="number" label="Год *" outlined dense />
          <q-select v-model="newForm.copy_from" :options="budgets.map((b) => ({ label: `Статьи сметы ${b.year} года`, value: b.year }))"
                    emit-value map-options clearable outlined dense label="Взять за основу" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="green-8" label="Создать" :loading="saving" @click="createBudget" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Статья -->
    <q-dialog v-model="itemDialog">
      <q-card style="width:480px;max-width:96vw">
        <q-card-section class="text-h6">{{ itemForm.id ? 'Статья' : 'Новая статья' }}</q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-select v-model="itemForm.section" :options="sections" emit-value map-options outlined dense label="Источник" />
          <q-input v-model="itemForm.name" label="Статья *" outlined dense />
          <q-toggle v-model="itemForm.byQty" label="Считать как количество × цена" />
          <div v-if="itemForm.byQty" class="row q-col-gutter-sm">
            <q-input v-model="itemForm.quantity" type="number" label="Количество" outlined dense class="col-4" />
            <q-input v-model="itemForm.unit" label="Единица" outlined dense class="col-3" hint="мес, рейс…" />
            <q-input v-model="itemForm.unit_price" type="number" label="Цена, ₽" outlined dense class="col-5" />
          </div>
          <q-input v-else v-model="itemForm.amount" type="number" label="Сумма, ₽ *" outlined dense />
          <q-input v-model="itemForm.justification" type="textarea" autogrow label="Обоснование"
                   hint="Договор, счёт, расчёт — попадёт в ФЭО" outlined dense />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="green-8" label="Сохранить" :loading="saving" @click="saveItem" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Утверждение -->
    <q-dialog v-model="approveDialog">
      <q-card style="min-width:320px">
        <q-card-section class="text-h6">Утверждение сметы</q-card-section>
        <q-card-section class="q-gutter-sm">
          <div class="text-body2">Отметьте решение общего собрания. После этого смета не меняется, и по ней можно начислить членский взнос.</div>
          <q-input v-model="approveForm.approved_at" type="date" label="Дата собрания *" outlined dense />
          <q-input v-model="approveForm.protocol_number" label="Номер протокола" outlined dense />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="green-8" label="Утвердить" :disable="!approveForm.approved_at" :loading="saving" @click="approve" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Начисление по смете -->
    <q-dialog v-model="chargeDialog">
      <q-card style="min-width:320px">
        <q-card-section class="text-h6">Членский взнос по смете</q-card-section>
        <q-card-section class="q-gutter-sm">
          <div class="text-body2">
            {{ money(calc.rate) }} {{ budget?.basis === 'per_sotka' ? 'за сотку' : 'с участка' }} — всем участкам с собственником,
            в период «{{ year }} год». Уже начисленным повторно не начислится.
          </div>
          <q-input v-model="chargeForm.due_date" type="date" label="Оплатить до" outlined dense />
          <q-input v-model="chargeForm.penalty_percent" type="number" label="Пени после срока, %" outlined dense />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="green-8" label="Начислить" :loading="saving" @click="chargeMembership" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Расход -->
    <q-dialog v-model="expenseDialog">
      <q-card style="width:460px;max-width:96vw">
        <q-card-section class="text-h6">Расход</q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-input v-model="expenseForm.date" type="date" label="Дата *" outlined dense />
          <q-input v-model="expenseForm.amount" type="number" label="Сумма, ₽ *" outlined dense />
          <q-select v-model="expenseForm.item" :options="itemOptions" emit-value map-options clearable
                    outlined dense label="Статья сметы" hint="Пусто — вне сметы" />
          <q-input v-model="expenseForm.counterparty" label="Кому" outlined dense />
          <q-input v-model="expenseForm.document" label="Документ (№ и дата счёта, акта, чека)" outlined dense />
          <q-input v-model="expenseForm.description" label="Описание" outlined dense />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="green-8" label="Сохранить" :loading="saving" @click="saveExpense" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import api from 'src/api/client'
import { useAuthStore } from 'stores/auth'

const $q = useQuasar()
const auth = useAuthStore()
const thisYear = new Date().getFullYear()

const tab = ref('budget')
const year = ref(thisYear)
const budgets = ref([])
const budget = ref(null)
const exec = ref(null)
const expenses = ref([])
const saving = ref(false)

const sections = [
  { value: 'membership', label: 'За счёт членских взносов' },
  { value: 'target', label: 'За счёт целевых взносов' },
]
const basisOptions = [
  { value: 'flat', label: 'Поровну с участка' },
  { value: 'per_sotka', label: 'По площади (за сотку)' },
]

const approved = computed(() => budget.value?.status === 'approved')
const calc = computed(() => budget.value?.calc || {})
const yearOptions = computed(() => {
  const years = new Set(budgets.value.map((b) => b.year))
  years.add(thisYear)
  years.add(year.value)
  return [...years].sort((a, b) => b - a).map((y) => ({ label: String(y), value: y }))
})
const itemOptions = computed(() => (budget.value?.items || [])
  .map((i) => ({ label: i.name, value: i.id })))

function money(v) {
  if (v === null || v === undefined || v === '') return '—'
  return Number(v).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' ₽'
}
function fmtDate(v) { return v ? v.split('-').reverse().join('.') : '' }
function calcText(i) {
  if (i.quantity === null || i.unit_price === null) return '—'
  return `${Number(i.quantity)} ${i.unit || ''} × ${money(i.unit_price)}`
}
function itemsOf(section) { return (budget.value?.items || []).filter((i) => i.section === section) }
function errText(e) {
  const d = e.response?.data
  if (d && typeof d === 'object') return Object.values(d).flat().join(' ')
  return 'Не получилось'
}

async function loadBudgets() {
  const { data } = await api.get('/budgets/', { params: { page_size: 50 } })
  budgets.value = data.results || data
}

async function loadBudget() {
  budget.value = budgets.value.find((b) => b.year === year.value) || null
  if (budget.value) {
    const { data } = await api.get(`/budgets/${budget.value.id}/`)
    budget.value = data
  }
  await Promise.all([loadExecution(), loadExpenses()])
}

async function loadExecution() {
  exec.value = budget.value ? (await api.get(`/budgets/${budget.value.id}/execution/`)).data : null
}

async function loadExpenses() {
  const { data } = await api.get('/expenses/', { params: { year: year.value, page_size: 500 } })
  expenses.value = data.results || data
}

async function refresh() {
  await loadBudgets()
  await loadBudget()
}

// ── смета ──
const newDialog = ref(false)
const newForm = ref({ year: thisYear + 1, copy_from: null })
function openNewBudget() {
  const last = budgets.value[0]?.year
  newForm.value = { year: last ? last + 1 : thisYear, copy_from: last || null }
  newDialog.value = true
}
async function createBudget() {
  saving.value = true
  try {
    const body = { year: newForm.value.year }
    if (newForm.value.copy_from) body.copy_from = newForm.value.copy_from
    await api.post('/budgets/', body)
    newDialog.value = false
    year.value = newForm.value.year
    tab.value = 'budget'
    await refresh()
  } catch (e) { $q.notify({ type: 'negative', message: errText(e) }) } finally { saving.value = false }
}
async function saveBasis(basis) {
  try {
    const { data } = await api.patch(`/budgets/${budget.value.id}/`, { basis })
    budget.value = data
  } catch (e) { $q.notify({ type: 'negative', message: errText(e) }) }
}
function deleteBudget() {
  $q.dialog({ title: 'Удалить смету?', message: `Черновик сметы на ${year.value} год со всеми статьями.`, cancel: true })
    .onOk(async () => {
      try { await api.delete(`/budgets/${budget.value.id}/`); await refresh() } catch (e) { $q.notify({ type: 'negative', message: errText(e) }) }
    })
}

const itemDialog = ref(false)
const itemForm = ref({})
function openItem(item, section) {
  itemForm.value = item
    ? { ...item, byQty: item.quantity !== null && item.unit_price !== null }
    : { section, name: '', byQty: false, quantity: '', unit: '', unit_price: '', amount: '', justification: '' }
  itemDialog.value = true
}
async function saveItem() {
  saving.value = true
  const f = itemForm.value
  const body = {
    budget: budget.value.id, section: f.section, name: f.name, justification: f.justification || '',
    quantity: f.byQty && f.quantity !== '' ? f.quantity : null,
    unit: f.byQty ? f.unit || '' : '',
    unit_price: f.byQty && f.unit_price !== '' ? f.unit_price : null,
  }
  if (!f.byQty) body.amount = f.amount
  try {
    if (f.id) await api.patch(`/budget-items/${f.id}/`, body)
    else await api.post('/budget-items/', body)
    itemDialog.value = false
    await loadBudget()
  } catch (e) { $q.notify({ type: 'negative', message: errText(e) }) } finally { saving.value = false }
}
function deleteItem(item) {
  $q.dialog({ title: 'Удалить статью?', message: item.name, cancel: true }).onOk(async () => {
    try { await api.delete(`/budget-items/${item.id}/`); await loadBudget() } catch (e) { $q.notify({ type: 'negative', message: errText(e) }) }
  })
}

const approveDialog = ref(false)
const approveForm = ref({ approved_at: '', protocol_number: '' })
async function approve() {
  saving.value = true
  try {
    const { data } = await api.post(`/budgets/${budget.value.id}/approve/`, approveForm.value)
    budget.value = data
    approveDialog.value = false
    await loadBudgets()
  } catch (e) { $q.notify({ type: 'negative', message: errText(e) }) } finally { saving.value = false }
}
async function unapprove() {
  try {
    const { data } = await api.post(`/budgets/${budget.value.id}/unapprove/`)
    budget.value = data
    await loadBudgets()
  } catch (e) { $q.notify({ type: 'negative', message: errText(e) }) }
}

const chargeDialog = ref(false)
const chargeForm = ref({ due_date: '', penalty_percent: 20 })
async function chargeMembership() {
  saving.value = true
  try {
    const body = { penalty_percent: chargeForm.value.penalty_percent }
    if (chargeForm.value.due_date) body.due_date = chargeForm.value.due_date
    const { data } = await api.post(`/budgets/${budget.value.id}/charge-membership/`, body)
    chargeDialog.value = false
    const skipped = (data.skipped_no_owner || []).length + (data.skipped_no_area || []).length
    $q.notify({
      type: 'positive', multiLine: true, timeout: 8000,
      message: `Начислено участкам: ${data.created}` + (skipped ? `. Пропущено (без собственника или площади): ${skipped}` : ''),
    })
    await loadExecution()
  } catch (e) { $q.notify({ type: 'negative', message: errText(e) }) } finally { saving.value = false }
}

// ── расходы ──
const expenseDialog = ref(false)
const expenseForm = ref({})
function openExpense() {
  const today = new Date().toISOString().slice(0, 10)
  expenseForm.value = { date: today.startsWith(String(year.value)) ? today : `${year.value}-01-01`,
    amount: '', item: null, counterparty: '', document: '', description: '' }
  expenseDialog.value = true
}
async function saveExpense() {
  saving.value = true
  try {
    await api.post('/expenses/', expenseForm.value)
    expenseDialog.value = false
    await Promise.all([loadExpenses(), loadExecution()])
  } catch (e) { $q.notify({ type: 'negative', message: errText(e) }) } finally { saving.value = false }
}
function deleteExpense(e) {
  $q.dialog({ title: 'Удалить расход?', message: `${fmtDate(e.date)} — ${money(e.amount)}`, cancel: true }).onOk(async () => {
    await api.delete(`/expenses/${e.id}/`)
    await Promise.all([loadExpenses(), loadExecution()])
  })
}

// ── выгрузка ──
const accFrom = ref(`${thisYear}-01-01`)
const accTo = ref(new Date().toISOString().slice(0, 10))

async function download(url, name) {
  try {
    const { data } = await api.get(url, { responseType: 'blob' })
    const href = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = href
    a.download = name
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(href), 1000)
  } catch {
    $q.notify({ type: 'negative', message: 'Файл не скачался' })
  }
}

onMounted(refresh)
</script>
