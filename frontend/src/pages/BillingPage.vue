<template>
  <q-page class="q-pa-md">
    <!-- Выбор периода -->
    <q-select
      v-model="selectedPeriod"
      :options="periods"
      option-label="label"
      option-value="id"
      emit-value map-options
      label="Период"
      outlined dense
      class="q-mb-md"
      @update:model-value="onPeriodChange"
    />

    <q-tabs v-model="tab" dense align="left" class="q-mb-md" active-color="green-8" indicator-color="green-8">
      <q-tab name="debt" label="Долги" />
      <q-tab name="charges" label="Начисления" />
      <q-tab name="payments" label="Платежи" />
    </q-tabs>

    <!-- Долги -->
    <q-tab-panels v-model="tab" animated>
      <q-tab-panel name="debt" class="q-pa-none">
        <div class="row q-mb-sm q-gutter-sm" v-if="auth.isChairman || auth.isTreasurer">
          <q-btn size="sm" outline color="green-8" icon="add" label="Членский взнос" @click="bulkMembershipDialog = true" />
          <q-btn size="sm" outline color="blue-8" icon="add" label="Целевой взнос" @click="bulkTargetDialog = true" />
          <q-btn
            size="sm" outline color="deep-orange-8" icon="gavel"
            label="Начислить пени" :loading="actionLoading"
            @click="confirmPenalties"
          />
        </div>

        <q-list separator bordered rounded>
          <q-item v-for="d in debtSummary" :key="d.plot_id">
            <q-item-section>
              <q-item-label>Уч. №{{ d.plot_number }}{{ ownerSuffix(d) }}</q-item-label>
              <q-item-label caption>
                Нач: {{ formatMoney(d.total_charged) }} · Опл: {{ formatMoney(d.total_paid) }}
              </q-item-label>
            </q-item-section>
            <q-item-section side>
              <span :class="d.debt > 0 ? 'debt-amount' : 'paid-amount'">
                {{ d.debt > 0 ? formatMoney(d.debt) + ' ₽' : '✓' }}
              </span>
            </q-item-section>
          </q-item>
          <q-item v-if="!debtSummary.length">
            <q-item-section class="text-center text-grey-6">Нет данных за период</q-item-section>
          </q-item>
        </q-list>
      </q-tab-panel>

      <!-- Начисления -->
      <q-tab-panel name="charges" class="q-pa-none">
        <q-banner v-if="chargesTruncated" dense class="bg-orange-2 q-mb-sm rounded-borders">
          <template #avatar><q-icon name="warning" color="orange-9" /></template>
          Показаны первые {{ charges.length }} начислений из {{ chargesTotal }}.
          Остальные в список не поместились — выгрузите ведомость на странице
          «Отчёты», там все.
        </q-banner>
        <q-list separator bordered rounded>
          <q-item v-for="c in charges" :key="c.id">
            <q-item-section>
              <q-item-label>{{ c.charge_type_name }}</q-item-label>
              <q-item-label caption>
                Уч. №{{ c.plot_number }}
                <template v-if="c.member_name"> · {{ c.member_name }}</template>
                · {{ c.description }}
              </q-item-label>
              <q-item-label v-if="c.due_date" caption>
                <span :class="c.is_overdue ? 'text-negative text-weight-medium' : ''">
                  Оплатить до {{ formatDate(c.due_date) }}
                  <template v-if="c.is_overdue"> · просрочено</template>
                </span>
                <template v-if="Number(c.penalty_percent) > 0">
                  · пени {{ Number(c.penalty_percent) }} %
                </template>
              </q-item-label>
            </q-item-section>
            <q-item-section side>{{ formatMoney(c.amount) }} ₽</q-item-section>
          </q-item>
          <q-item v-if="!charges.length">
            <q-item-section class="text-center text-grey-6">Нет начислений</q-item-section>
          </q-item>
        </q-list>
      </q-tab-panel>

      <!-- Платежи -->
      <q-tab-panel name="payments" class="q-pa-none">
        <q-banner v-if="paymentsTruncated" dense class="bg-orange-2 q-mb-sm rounded-borders">
          <template #avatar><q-icon name="warning" color="orange-9" /></template>
          Показаны первые {{ payments.length }} платежей из {{ paymentsTotal }}.
        </q-banner>
        <q-btn
          v-if="auth.isTreasurer || auth.isChairman"
          color="green-8" icon="add" label="Внести платёж"
          class="q-mb-md full-width" outline
          @click="paymentDialog = true"
        />
        <q-list separator bordered rounded>
          <q-item v-for="p in payments" :key="p.id">
            <q-item-section>
              <q-item-label>{{ p.charge_info }}</q-item-label>
              <q-item-label caption>{{ p.date }} · {{ methodLabel(p.method) }}</q-item-label>
            </q-item-section>
            <q-item-section side class="paid-amount">{{ formatMoney(p.amount) }} ₽</q-item-section>
          </q-item>
          <q-item v-if="!payments.length">
            <q-item-section class="text-center text-grey-6">Нет платежей</q-item-section>
          </q-item>
        </q-list>
      </q-tab-panel>
    </q-tab-panels>

    <!-- Диалог: членский взнос -->
    <q-dialog v-model="bulkMembershipDialog" persistent @show="loadPlots">
      <q-card style="min-width:340px;max-width:480px">
        <q-card-section class="text-h6">Начислить членские взносы</q-card-section>
        <q-card-section>
          <q-form class="q-gutter-sm">
            <q-option-group
              v-model="membershipForm.basis"
              :options="basisOptions"
              color="green-8" dense
            />
            <q-input
              v-if="membershipForm.basis === 'flat'"
              v-model="membershipForm.amount"
              label="Сумма на участок (₽) *" outlined dense type="number"
            />
            <q-input
              v-else
              v-model="membershipForm.rate"
              label="Ставка за сотку (₽) *" outlined dense type="number"
            />
            <div
              v-if="membershipForm.basis === 'per_sotka'"
              class="text-caption text-grey-8 charge-preview"
            >{{ membershipPreview }}</div>
            <q-input
              v-model="membershipForm.due_date"
              label="Оплатить до" outlined dense type="date"
              hint="Необязательно. После этой даты на остаток долга один раз начисляются пени."
            />
            <q-input
              v-if="membershipForm.due_date"
              v-model="membershipForm.penalty_percent"
              label="Пени, % от остатка долга" outlined dense type="number"
            />
            <q-input v-model="membershipForm.description" label="Описание" outlined dense />
          </q-form>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="green-8" label="Начислить всем" :loading="actionLoading" @click="createMembership" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Диалог: целевой взнос -->
    <q-dialog v-model="bulkTargetDialog" persistent @show="loadPlots">
      <q-card style="min-width:340px;max-width:480px">
        <q-card-section class="text-h6">Начислить целевой взнос</q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-select
            v-model="targetForm.charge_type_id"
            :options="chargeTypeOptions"
            :loading="chargeTypesLoading"
            option-label="label" option-value="value"
            emit-value map-options
            label="Вид начисления *"
            outlined dense
            use-input fill-input hide-selected input-debounce="0"
            hint="Впишите название и нажмите Enter, чтобы завести новый вид"
            @filter="filterChargeTypes"
            @new-value="createChargeType"
          />
          <q-option-group
            v-model="targetForm.scope"
            :options="scopeOptions"
            color="blue-8" dense inline
          />
          <div v-if="targetForm.scope === 'member'" class="text-caption text-grey-8 charge-preview">
            Один взнос на человека, сколько бы участков у него ни было.
            Совладельцы общего участка платят каждый за себя.
            По соткам «за члена» не считается — только фиксированной суммой.
          </div>
          <q-option-group
            v-if="targetForm.scope === 'plot'"
            v-model="targetForm.basis"
            :options="basisOptions"
            color="blue-8" dense
          />
          <q-input
            v-if="targetForm.basis === 'flat' || targetForm.scope === 'member'"
            v-model="targetForm.amount"
            :label="targetForm.scope === 'member' ? 'Сумма с члена (₽) *' : 'Сумма на участок (₽) *'"
            outlined dense type="number"
          />
          <q-input
            v-else
            v-model="targetForm.rate"
            label="Ставка за сотку (₽) *" outlined dense type="number"
          />
          <div
            v-if="targetForm.scope === 'plot' && targetForm.basis === 'per_sotka'"
            class="text-caption text-grey-8 charge-preview"
          >{{ targetPreview }}</div>
          <q-input
            v-model="targetForm.due_date"
            label="Оплатить до" outlined dense type="date"
            hint="Необязательно. После этой даты на остаток долга один раз начисляются пени."
          />
          <q-input
            v-if="targetForm.due_date"
            v-model="targetForm.penalty_percent"
            label="Пени, % от остатка долга" outlined dense type="number"
          />
          <q-input v-model="targetForm.description" label="Описание" outlined dense />

          <q-option-group
            v-model="targetScope"
            :options="targetForm.scope === 'member'
              ? [
                { label: 'Всем членам', value: 'all' },
                { label: 'Владельцам выбранных участков', value: 'some' },
              ]
              : [
                { label: 'Всем участкам', value: 'all' },
                { label: 'Выбранным участкам', value: 'some' },
              ]"
            color="blue-8" dense inline
          />
          <q-select
            v-if="targetScope === 'some'"
            v-model="targetForm.plot_ids"
            :options="plotOptions"
            :loading="plotsLoading"
            option-label="label" option-value="value"
            emit-value map-options
            multiple use-chips use-input input-debounce="0"
            label="Участки"
            outlined dense
            @filter="filterPlots"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="blue-8" label="Начислить" :loading="actionLoading" @click="createTarget" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Диалог: платёж -->
    <q-dialog v-model="paymentDialog" persistent>
      <q-card style="min-width:320px">
        <q-card-section class="text-h6">Внести платёж</q-card-section>
        <q-card-section>
          <q-form class="q-gutter-sm">
            <q-select v-model="payForm.charge" label="Начисление" outlined dense :options="chargeOptions" emit-value map-options />
            <q-input v-model="payForm.amount" label="Сумма (₽) *" outlined dense type="number" />
            <q-input v-model="payForm.date" label="Дата" outlined dense type="date" />
            <q-select v-model="payForm.method" label="Способ" outlined dense :options="methodOptions" emit-value map-options />
          </q-form>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="green-8" label="Сохранить" :loading="actionLoading" @click="createPayment" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useQuasar } from 'quasar'
import { useAuthStore } from 'stores/auth'
import api from 'src/api/client'

const $q = useQuasar()
const auth = useAuthStore()

const tab = ref('debt')
const periods = ref([])
const selectedPeriod = ref(null)
const debtSummary = ref([])
const charges = ref([])
const payments = ref([])
// Сколько записей за период есть всего. Список тянется страницей, и без
// этого числа он молча обрывался: казначей с полутора сотнями участков
// видел часть начислений и был уверен, что видит все.
const chargesTotal = ref(0)
const paymentsTotal = ref(0)
const chargesTruncated = computed(() => chargesTotal.value > charges.value.length)
const paymentsTruncated = computed(() => paymentsTotal.value > payments.value.length)
const actionLoading = ref(false)
const bulkMembershipDialog = ref(false)
const bulkTargetDialog = ref(false)
const paymentDialog = ref(false)
// Членские в большинстве товариществ считают от площади, целевые чаще
// одной суммой на участок — отсюда разные значения по умолчанию.
const membershipForm = ref({
  basis: 'per_sotka', amount: '', rate: '', description: '',
  due_date: '', penalty_percent: '20',
})
const targetForm = ref({
  charge_type_id: null, scope: 'plot', basis: 'flat', amount: '', rate: '',
  description: '', plot_ids: [], due_date: '', penalty_percent: '20',
})
const scopeOptions = [
  { label: 'За участок', value: 'plot' },
  { label: 'За члена товарищества', value: 'member' },
]
const basisOptions = [
  { label: 'Фиксированная сумма на участок', value: 'flat' },
  { label: 'Ставка за сотку', value: 'per_sotka' },
]
const targetScope = ref('all')
const allChargeTypes = ref([])
const chargeTypeOptions = ref([])
const chargeTypesLoading = ref(false)
const allPlots = ref([])
const plotOptions = ref([])
const plotsLoading = ref(false)
const payForm = ref({ charge: null, amount: '', date: new Date().toISOString().slice(0, 10), method: 'cash' })
const chargeOptions = ref([])

const methodOptions = [
  { label: 'Наличные', value: 'cash' },
  { label: 'Банк', value: 'bank' },
  { label: 'СБП', value: 'sbp' },
  { label: 'Карта', value: 'card' },
]
function methodLabel(m) { return methodOptions.find((o) => o.value === m)?.label || m }
function formatMoney(v) { return v ? Number(v).toLocaleString('ru-RU', { maximumFractionDigits: 0 }) : '0' }
function formatDate(v) { return v ? v.split('-').reverse().join('.') : '' }

// Сводка долгов отдаёт поле owner_name, а не member_name: шаблон читал
// несуществующее поле и во всех строках печатался голый номер участка
// с висящим тире. Участок без собственника сервер помечает прочерком —
// дублировать его вторым тире незачем.
function ownerSuffix(row) {
  const name = (row.owner_name || '').trim()
  if (!name || name === '—') return ' — без собственника'
  return ` — ${name}`
}

// Срок и ставку пеней шлём только вместе: без срока процент не от чего
// отсчитывать, и сервер его всё равно обнулит.
function penaltyPayload(form) {
  if (!form.due_date) return {}
  return { due_date: form.due_date, penalty_percent: form.penalty_percent || 0 }
}

// Годовой период (month = null) давал «2026-null»: String(null) — это
// строка «null» длиной четыре, и padStart её не трогает. Статус заодно
// показывался по-английски, прямо как в базе.
function periodLabel(p) {
  const name = p.month
    ? `${p.year}-${String(p.month).padStart(2, '0')}`
    : `${p.year} год`
  const status = p.status === 'closed' ? 'закрыт' : 'открыт'
  return `${name} (${status})`
}

async function loadPeriods() {
  const { data } = await api.get('/billing/periods/?page_size=24&ordering=-year,-month')
  periods.value = data.results.map((p) => ({ ...p, label: periodLabel(p) }))
  if (periods.value.length) {
    selectedPeriod.value = periods.value[0].id
    await onPeriodChange(selectedPeriod.value)
  }
}

// Порядок строк на вкладке «Начисления».
// Номер участка — строка («12а», «а-15»), и база сравнивает его
// посимвольно: 1, 10, 100, 101 … 2. Сравниваем с numeric: true — так
// 2 встаёт перед 10, а буквенные номера не ломаются.
// Внутри участка пени идут сразу под тем начислением, за просрочку
// которого они выписаны: группой считается id исходного начисления.
// Раньше порядок внутри участка не задавался вовсе, и пени прыгали то
// выше взноса, то ниже.
function chargeOrder(a, b) {
  const byPlot = String(a.plot_number).localeCompare(
    String(b.plot_number), 'ru', { numeric: true },
  )
  if (byPlot) return byPlot
  const groupA = a.penalty_for || a.id
  const groupB = b.penalty_for || b.id
  if (groupA !== groupB) return groupA - groupB
  return (a.penalty_for ? 1 : 0) - (b.penalty_for ? 1 : 0)
}

async function onPeriodChange(pid) {
  if (!pid) return
  const [debt, ch, pay] = await Promise.all([
    api.get(`/billing/periods/${pid}/debt_summary/`),
    // 500 — предел, который разрешает StandardPagination. Больше одним
    // запросом не отдадут, поэтому ниже сверяем длину с count и, если
    // не влезло, говорим об этом вслух.
    api.get(`/billing/charges/?period=${pid}&page_size=500`),
    api.get(`/billing/payments/?period=${pid}&page_size=500`),
  ])
  debtSummary.value = debt.data
  charges.value = [...(ch.data.results || ch.data)].sort(chargeOrder)
  payments.value = pay.data.results || pay.data
  chargesTotal.value = ch.data.count ?? charges.value.length
  paymentsTotal.value = pay.data.count ?? payments.value.length
  chargeOptions.value = (ch.data.results || ch.data).map((c) => ({
    label: `Уч.${c.plot_number} ${c.charge_type_name} ${formatMoney(c.amount)}₽`,
    value: c.id,
  }))
}

// Сообщение с сервера важнее общего «Ошибка»: именно так пользователь
// узнаёт, что, например, не выбрано СНТ или вид начисления чужой.
function errText(e, fallback) {
  const d = e?.response?.data
  if (!d) return fallback
  if (typeof d === 'string') return d
  if (typeof d.detail === 'string') return d.detail
  if (Array.isArray(d.detail)) return d.detail.join(' ')
  if (Array.isArray(d)) return d.join(' ')
  const first = Object.values(d)[0]
  if (Array.isArray(first)) return first.join(' ')
  if (typeof first === 'string') return first
  return fallback
}

async function loadChargeTypes() {
  chargeTypesLoading.value = true
  try {
    const { data } = await api.get('/billing/charge-types/?page_size=200')
    const list = data.results || data
    allChargeTypes.value = list
      .filter((t) => t.category === 'target' && t.is_active)
      .map((t) => ({ label: t.name, value: t.id }))
    chargeTypeOptions.value = allChargeTypes.value
  } catch (e) {
    $q.notify({ type: 'negative', message: errText(e, 'Не удалось загрузить виды начислений') })
  } finally { chargeTypesLoading.value = false }
}

// Целевые взносы каждый раз новые («ремонт дороги», «замена трансформатора»),
// заводить их заранее в отдельном разделе неудобно — поэтому вид начисления
// создаётся прямо отсюда.
function filterChargeTypes(val, update) {
  update(() => {
    const q = (val || '').toLowerCase()
    chargeTypeOptions.value = q
      ? allChargeTypes.value.filter((t) => t.label.toLowerCase().includes(q))
      : allChargeTypes.value
  })
}

async function createChargeType(name, done) {
  const title = (name || '').trim()
  if (!title) { done(null); return }
  // Ввели название уже существующего вида — выбираем его, а не заводим
  // второй такой же: иначе в списке копятся дубли «Ремонт дороги».
  const existing = allChargeTypes.value.find(
    (t) => t.label.toLowerCase() === title.toLowerCase(),
  )
  if (existing) { done(existing.value); return }
  try {
    const { data } = await api.post('/billing/charge-types/', {
      name: title, category: 'target', is_active: true,
    })
    const opt = { label: data.name, value: data.id }
    allChargeTypes.value = [...allChargeTypes.value, opt]
    chargeTypeOptions.value = allChargeTypes.value
    done(opt.value)
  } catch (e) {
    done(null)
    $q.notify({ type: 'negative', message: errText(e, 'Не удалось создать вид начисления') })
  }
}

async function loadPlots() {
  if (allPlots.value.length) return
  plotsLoading.value = true
  try {
    const { data } = await api.get('/plots/?page_size=500')
    allPlots.value = (data.results || data).map((p) => ({
      label: `Уч. №${p.number}${p.current_owner ? ' — ' + p.current_owner.full_name : ''}`,
      value: p.id,
      number: String(p.number),
      area: p.area_sotok === null ? 0 : Number(p.area_sotok),
      hasOwner: !!p.current_owner,
    }))
  } finally { plotsLoading.value = false }
}

// Предварительный расчёт до нажатия «Начислить». Считаем ту же формулу,
// что и сервер, чтобы казначей увидел порядок суммы и — главное —
// сколько участков останется без начисления из-за пустой площади.
// Сервер всё равно пересчитает сам: это подсказка, а не источник правды.
function areaPreview(rate, plots) {
  if (!plots.length) return 'Список участков ещё загружается…'
  const value = Number(rate)
  if (!value || value <= 0) return 'Укажите ставку за сотку — покажу расчёт.'
  const withArea = plots.filter((p) => p.area > 0)
  const totalArea = withArea.reduce((sum, p) => sum + p.area, 0)
  const missing = plots.length - withArea.length
  let text = `Участков с заполненной площадью: ${withArea.length} из ${plots.length}.`
    + ` Всего ${totalArea.toFixed(2)} сот.`
    + ` Начислим ориентировочно ${formatMoney(value * totalArea)} ₽.`
  if (missing) {
    text += ` У ${missing} участков площадь не заполнена — им начисление не уйдёт.`
  }
  return text
}

const membershipPreview = computed(
  // Членский взнос начисляется только участкам с текущим собственником:
  // на остальные сервер его не выпишет, и в расчёт их включать нечестно.
  () => areaPreview(membershipForm.value.rate, allPlots.value.filter((p) => p.hasOwner)),
)

const targetPreview = computed(() => {
  const ids = targetScope.value === 'some' ? (targetForm.value.plot_ids || []) : null
  const plots = ids ? allPlots.value.filter((p) => ids.includes(p.value)) : allPlots.value
  return areaPreview(targetForm.value.rate, plots)
})

function filterPlots(val, update) {
  loadPlots().then(() => {
    update(() => {
      const q = (val || '').toLowerCase()
      plotOptions.value = q
        ? allPlots.value.filter((p) => p.label.toLowerCase().includes(q))
        : allPlots.value
    })
  })
}

async function createTarget() {
  if (!targetForm.value.charge_type_id) {
    $q.notify({ type: 'warning', message: 'Выберите вид начисления' })
    return
  }
  // «За члена» — всегда фиксированной суммой, сервер иначе откажет.
  const targetByArea = targetForm.value.scope === 'plot'
    && targetForm.value.basis === 'per_sotka'
  if (!Number(targetByArea ? targetForm.value.rate : targetForm.value.amount)) {
    $q.notify({
      type: 'warning',
      message: targetByArea ? 'Укажите ставку за сотку' : 'Укажите сумму',
    })
    return
  }
  const plotIds = targetScope.value === 'some' ? targetForm.value.plot_ids : null
  if (targetScope.value === 'some' && !plotIds.length) {
    $q.notify({ type: 'warning', message: 'Выберите хотя бы один участок' })
    return
  }
  actionLoading.value = true
  try {
    const { data } = await api.post(
      `/billing/periods/${selectedPeriod.value}/create_target_charges/`,
      {
        charge_type_id: targetForm.value.charge_type_id,
        scope: targetForm.value.scope,
        basis: targetByArea ? 'per_sotka' : 'flat',
        // Шлём только то поле, которое относится к выбранному способу:
        // сериализатор вторым всё равно не воспользуется, а лишнее
        // значение в теле запроса путает при разборе логов.
        ...(targetByArea
          ? { rate: targetForm.value.rate }
          : { amount: targetForm.value.amount }),
        description: targetForm.value.description,
        // plot_ids не шлём вовсе, если начисляем всем: сериализатор
        // трактует отсутствие поля как «все участки».
        ...(plotIds ? { plot_ids: plotIds } : {}),
        ...penaltyPayload(targetForm.value),
      },
    )
    bulkTargetDialog.value = false
    targetForm.value = {
      charge_type_id: null, scope: 'plot', basis: 'flat', amount: '', rate: '',
      description: '', plot_ids: [], due_date: '', penalty_percent: '20',
    }
    targetScope.value = 'all'
    await onPeriodChange(selectedPeriod.value)
    notifyCharged(data.created, data.no_owner,
                  data.scope === 'member'
                    ? 'С них взыскать не с кого — взнос не выписан'
                    : 'Начисление есть, но в личном кабинете его никто не увидит',
                  data.skipped_no_area,
                  data.scope === 'member' ? 'членам' : 'участкам')
  } catch (e) {
    $q.notify({ type: 'negative', message: errText(e, 'Не удалось начислить') })
  } finally { actionLoading.value = false }
}

// Участки без текущего собственника — отдельным сообщением, которое не
// гаснет само. Начисление на такой участок в личный кабинет не попадёт:
// показывать его некому. Молчать об этом нельзя — казначей уверен, что
// начислил, а человек ничего не видит и идёт разбираться.
function notifyCharged(created, noOwner, warning, noArea, whom = 'участков') {
  const orphans = noOwner || []
  // Участки без заполненной площади при расчёте по соткам: им сумму
  // считать не из чего, начисления не будет вообще. Это не то же
  // самое, что участок без собственника, и сказать надо отдельно.
  const arealess = noArea || []
  if (!orphans.length && !arealess.length) {
    $q.notify({ type: 'positive', message: `Начислено ${whom}: ${created}` })
    return
  }
  let message = `Начислено ${whom}: ${created}. `
  if (orphans.length) {
    message += `Без собственника: ${orphans.length} (${orphans.join(', ')}). ${warning} `
  }
  if (arealess.length) {
    message += `Без заполненной площади: ${arealess.length} (${arealess.join(', ')}). `
      + 'Им взнос не начислен — впишите площадь на странице «Участки» и повторите.'
  }
  $q.notify({
    type: 'warning',
    timeout: 0,
    multiLine: true,
    actions: [{ label: 'Понятно', color: 'white' }],
    message: message.trim(),
  })
}

async function createMembership() {
  const byArea = membershipForm.value.basis === 'per_sotka'
  if (!Number(byArea ? membershipForm.value.rate : membershipForm.value.amount)) {
    $q.notify({
      type: 'warning',
      message: byArea ? 'Укажите ставку за сотку' : 'Укажите сумму',
    })
    return
  }
  actionLoading.value = true
  try {
    const { data } = await api.post(
      `/billing/periods/${selectedPeriod.value}/create_membership_charges/`,
      {
        basis: membershipForm.value.basis,
        ...(byArea
          ? { rate: membershipForm.value.rate }
          : { amount: membershipForm.value.amount }),
        description: membershipForm.value.description,
        ...penaltyPayload(membershipForm.value),
      },
    )
    bulkMembershipDialog.value = false
    await onPeriodChange(selectedPeriod.value)
    notifyCharged(data.created, data.skipped_no_owner,
                  'Им взнос не начислен — закрепите участок за членом СНТ',
                  data.skipped_no_area)
  } catch (e) { $q.notify({ type: 'negative', message: errText(e, 'Ошибка') }) }
  finally { actionLoading.value = false }
}

// Пени необратимы: снять начисление можно только руками, по одному.
// Поэтому спрашиваем подтверждение, а в тексте называем ставку и то,
// что считается она от остатка долга, а не от полной суммы взноса.
function confirmPenalties() {
  $q.dialog({
    title: 'Начислить пени',
    message: 'Пени начислятся один раз по каждому начислению, у которого '
      + 'прошёл срок оплаты и остался долг. Считаются от остатка долга. '
      + 'Тем, кто уже заплатил, ничего не начислится. Продолжить?',
    cancel: { label: 'Отмена', flat: true },
    ok: { label: 'Начислить', color: 'deep-orange-8' },
    persistent: true,
  }).onOk(applyPenalties)
}

async function applyPenalties() {
  actionLoading.value = true
  try {
    const { data } = await api.post('/billing/charges/apply_penalties/')
    await onPeriodChange(selectedPeriod.value)
    if (data.created) {
      $q.notify({
        type: 'warning',
        message: `Начислено пеней: ${data.created} на ${formatMoney(data.total)} ₽`,
      })
    } else if (!data.with_due_date) {
      // Поле «Оплатить до» появилось позже начислений, и у старых оно
      // пустое. Спокойное «просроченных нет» здесь вводит в заблуждение:
      // человек уходит уверенный, что пени выписаны.
      $q.notify({
        type: 'warning',
        timeout: 0,
        multiLine: true,
        actions: [{ label: 'Понятно', color: 'white' }],
        message: `Пени не начислены: ни у одного из ${data.without_due_date} `
          + 'начислений не заполнен срок оплаты. Срок ставится при создании '
          + 'начисления — поле «Оплатить до».',
      })
    } else {
      $q.notify({
        type: 'positive',
        message: 'Просроченных начислений нет — пени начислять не за что',
      })
    }
  } catch (e) {
    $q.notify({ type: 'negative', message: errText(e, 'Не удалось начислить пени') })
  } finally { actionLoading.value = false }
}

async function createPayment() {
  actionLoading.value = true
  try {
    await api.post('/billing/payments/', payForm.value)
    paymentDialog.value = false
    await onPeriodChange(selectedPeriod.value)
    $q.notify({ type: 'positive', message: 'Платёж внесён' })
  } catch (e) { $q.notify({ type: 'negative', message: errText(e, 'Ошибка') }) }
  finally { actionLoading.value = false }
}

onMounted(async () => {
  await loadPeriods()
  if (auth.isChairman || auth.isTreasurer) await loadChargeTypes()
})
</script>

<style scoped>
/* Предварительный расчёт по соткам: заметная плашка, а не сноска —
   именно здесь видно, скольким участкам начисление не уйдёт. */
.charge-preview {
  background: rgba(0, 0, 0, 0.04);
  border-left: 3px solid var(--q-primary);
  border-radius: 4px;
  padding: 8px 10px;
  line-height: 1.4;
}
</style>
