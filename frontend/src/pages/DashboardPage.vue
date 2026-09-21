<template>
  <q-page class="q-pa-md">
    <!-- Карточки статистики (только для управления) -->
    <div v-if="!auth.isMember" class="row q-col-gutter-md q-mb-md">
      <div class="col-6">
        <q-card flat bordered>
          <q-card-section class="text-center">
            <q-icon name="people" size="32px" color="green-8" />
            <div class="text-h5 text-weight-bold">{{ stats.members }}</div>
            <div class="text-caption text-grey-7">Членов</div>
          </q-card-section>
        </q-card>
      </div>
      <div class="col-6">
        <q-card flat bordered>
          <q-card-section class="text-center">
            <q-icon name="landscape" size="32px" color="blue-8" />
            <div class="text-h5 text-weight-bold">{{ stats.plots }}</div>
            <div class="text-caption text-grey-7">Участков</div>
          </q-card-section>
        </q-card>
      </div>
      <div class="col-6">
        <q-card flat bordered>
          <q-card-section class="text-center">
            <q-icon name="warning" size="32px" color="negative" />
            <div class="text-h5 text-weight-bold">{{ stats.debtors }}</div>
            <div class="text-caption text-grey-7">Должников</div>
          </q-card-section>
        </q-card>
      </div>
      <div class="col-6">
        <q-card flat bordered>
          <q-card-section class="text-center">
            <q-icon name="payments" size="32px" color="orange-8" />
            <div class="text-h5 text-weight-bold">{{ formatMoney(stats.totalDebt) }}</div>
            <div class="text-caption text-grey-7">Долг (₽)</div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Личный кабинет члена -->
    <div v-if="auth.isMember">
      <q-card flat bordered class="q-mb-md">
        <q-card-section>
          <div class="text-subtitle1 text-weight-bold">
            <q-icon name="account_circle" class="q-mr-xs" />
            {{ auth.user?.full_name || auth.user?.username }}
          </div>
          <div class="text-caption text-grey-7">{{ auth.user?.organization_name }}</div>
        </q-card-section>
      </q-card>

      <!-- Итог оплаты после возврата с формы провайдера -->
      <q-banner v-if="payResult" :class="payResult.ok ? 'bg-green-1' : 'bg-orange-1'"
                class="q-mb-md" rounded>
        <template #avatar>
          <q-icon :name="payResult.ok ? 'check_circle' : 'schedule'"
                  :color="payResult.ok ? 'positive' : 'orange-8'" />
        </template>
        {{ payResult.text }}
      </q-banner>

      <!-- Сводка: отдельно свет, отдельно всё остальное -->
      <div class="row q-col-gutter-sm q-mb-md" v-if="myDebts.length">
        <div class="col-6">
          <q-card flat bordered class="full-height">
            <q-card-section class="text-center q-pa-sm">
              <q-icon name="bolt" size="26px" color="orange-8" />
              <div class="text-h6 text-weight-bold debt-amount">
                {{ formatMoney(electricityDebt) }} ₽
              </div>
              <div class="text-caption text-grey-7">Электроэнергия</div>
              <div class="text-caption text-grey-6" v-if="lastReadingLabel">
                {{ lastReadingLabel }}
              </div>
            </q-card-section>
          </q-card>
        </div>
        <div class="col-6">
          <q-card flat bordered class="full-height">
            <q-card-section class="text-center q-pa-sm">
              <q-icon name="receipt_long" size="26px" color="green-8" />
              <div class="text-h6 text-weight-bold debt-amount">
                {{ formatMoney(otherDebt) }} ₽
              </div>
              <div class="text-caption text-grey-7">Взносы и прочее</div>
            </q-card-section>
          </q-card>
        </div>
      </div>

      <q-card flat bordered class="q-mb-md" v-if="myDebts.length">
        <q-card-section>
          <div class="row items-center q-mb-sm">
            <div class="text-subtitle2">Мои начисления</div>
            <q-space />
            <div class="text-subtitle2 debt-amount">{{ formatMoney(myDebtTotal) }} ₽</div>
          </div>
          <q-list separator dense>
            <q-item v-for="d in myDebts" :key="d.id">
              <q-item-section avatar>
                <q-icon
                  :name="d.category === 'electricity' ? 'bolt' : 'receipt_long'"
                  :color="d.category === 'electricity' ? 'orange-8' : 'green-8'"
                  size="20px"
                />
              </q-item-section>
              <q-item-section>
                <q-item-label>{{ d.charge_type_name }}</q-item-label>
                <q-item-label caption>{{ d.period_label }} · уч. {{ d.plot_number }}</q-item-label>
                <!-- Основание начисления за свет: за что именно эти деньги -->
                <q-item-label caption v-if="d.kwh" class="text-orange-9">
                  {{ formatKwh(d.kwh) }} кВт·ч × {{ formatTariff(d.tariff) }} ₽
                </q-item-label>
                <q-item-label caption v-if="Number(d.paid_amount) > 0" class="text-green-8">
                  оплачено {{ formatMoney(d.paid_amount) }} из {{ formatMoney(d.amount) }} ₽
                </q-item-label>
              </q-item-section>
              <q-item-section side class="debt-amount">{{ formatMoney(d.debt) }} ₽</q-item-section>
            </q-item>
          </q-list>

          <q-btn
            v-if="onlineAvailable"
            color="green-8"
            icon="payments"
            label="Оплатить"
            class="full-width q-mt-md"
            unelevated
            @click="openPayDialog"
          />
          <div v-else class="text-caption text-grey-6 q-mt-sm">
            Онлайн-оплата в этом СНТ не подключена — обратитесь к казначею.
          </div>
        </q-card-section>
      </q-card>

      <!-- Оплата: по умолчанию весь долг, но сумму можно уменьшить -->
      <q-dialog v-model="payDialog">
        <q-card style="min-width: 320px; max-width: 420px">
          <q-card-section class="bg-green-8 text-white">
            <div class="text-h6">Оплата</div>
            <div class="text-caption">Задолженность {{ formatMoney(myDebtTotal) }} ₽</div>
          </q-card-section>
          <q-card-section class="q-gutter-sm">
            <q-input
              v-model="payAmount"
              label="Сумма к оплате, ₽ *"
              outlined
              type="number"
              inputmode="decimal"
              min="1"
              :max="myDebtTotal"
              :error="!!payAmountError"
              :error-message="payAmountError"
            >
              <template #prepend><q-icon name="payments" /></template>
            </q-input>
            <div class="text-caption text-grey-7">
              Можно заплатить часть. Деньги погасят начисления по очереди,
              начиная с самых старых.
            </div>
            <q-btn
              flat dense size="sm" color="green-8"
              :label="`Вся сумма — ${formatMoney(myDebtTotal)} ₽`"
              @click="payAmount = String(myDebtTotal)"
            />
          </q-card-section>
          <q-card-actions align="right">
            <q-btn flat label="Отмена" v-close-popup />
            <q-btn
              color="green-8"
              label="Перейти к оплате"
              unelevated
              :loading="paying"
              :disable="!payAmountValid"
              @click="payDebt"
            />
          </q-card-actions>
        </q-card>
      </q-dialog>

      <q-card flat bordered class="q-mb-md" v-if="!myDebts.length && debtsLoaded">
        <q-card-section class="text-center text-grey-6">
          <q-icon name="check_circle" color="positive" size="28px" />
          <div class="q-mt-xs">Задолженности нет</div>
        </q-card-section>
      </q-card>
    </div>

    <!-- Быстрые ссылки -->
    <div class="row q-col-gutter-sm">
      <div class="col-6" v-if="!auth.isMember">
        <q-btn
          outline
          color="green-8"
          icon="receipt_long"
          label="Начисления"
          class="full-width"
          to="/billing"
        />
      </div>
      <div class="col-6" v-if="!auth.isMember">
        <q-btn
          outline
          color="orange-8"
          icon="bolt"
          label="Электроэнергия"
          class="full-width"
          to="/electricity"
        />
      </div>
      <div class="col-12">
        <q-btn
          outline
          color="blue-8"
          icon="speed"
          label="Передать показания счётчика"
          class="full-width"
          to="/meter-reading"
        />
      </div>
      <div class="col-12" v-if="!auth.isMember">
        <q-btn
          outline
          color="purple-8"
          icon="bar_chart"
          label="Отчёты"
          class="full-width"
          to="/reports"
        />
      </div>
    </div>
  </q-page>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useQuasar } from 'quasar'
import { useAuthStore } from 'stores/auth'
import api from 'src/api/client'

const auth = useAuthStore()
const route = useRoute()
const $q = useQuasar()

const stats = ref({ members: 0, plots: 0, debtors: 0, totalDebt: 0 })
const myDebts = ref([])
const myDebtTotal = ref(0)
const electricityDebt = ref(0)
const otherDebt = ref(0)
const meters = ref([])
const onlineAvailable = ref(false)
const debtsLoaded = ref(false)
const paying = ref(false)
const payResult = ref(null)
const payDialog = ref(false)
const payAmount = ref('')

function formatMoney(val) {
  if (!val) return '0'
  return Number(val).toLocaleString('ru-RU', { maximumFractionDigits: 0 })
}

function formatKwh(val) {
  return Number(val).toLocaleString('ru-RU', { maximumFractionDigits: 1 })
}

function formatTariff(val) {
  return Number(val).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// Последнее переданное показание — чтобы сумма за свет не выглядела
// взявшейся ниоткуда.
const lastReadingLabel = computed(() => {
  const withReading = meters.value.filter((m) => m.last_reading_date)
  if (!withReading.length) return ''
  const latest = withReading.reduce((a, b) =>
    a.last_reading_date > b.last_reading_date ? a : b,
  )
  const d = new Date(latest.last_reading_date)
  return `показание ${formatKwh(latest.last_reading_value)} от ${d.toLocaleDateString('ru-RU')}`
})

const payAmountError = computed(() => {
  if (payAmount.value === '') return ''
  const v = Number(payAmount.value)
  if (!Number.isFinite(v) || v <= 0) return 'Введите сумму больше нуля'
  if (v > Number(myDebtTotal.value)) return `Не больше ${formatMoney(myDebtTotal.value)} ₽`
  return ''
})

const payAmountValid = computed(
  () => payAmount.value !== '' && !payAmountError.value,
)

function openPayDialog() {
  // По умолчанию предлагаем весь долг: частичная оплата — это выбор,
  // а не то, что человек должен вводить каждый раз руками.
  payAmount.value = String(myDebtTotal.value)
  payDialog.value = true
}

async function loadMyDebt() {
  try {
    const { data } = await api.get('/payments/my-debt/')
    myDebts.value = data.charges || []
    myDebtTotal.value = Number(data.total_debt || 0)
    electricityDebt.value = Number(data.electricity_debt || 0)
    otherDebt.value = Number(data.other_debt || 0)
    meters.value = data.meters || []
    onlineAvailable.value = !!data.online_available
  } catch (e) {
    console.error(e)
  } finally {
    debtsLoaded.value = true
  }
}

async function payDebt() {
  paying.value = true
  try {
    // Сумму разносит по начислениям сервер; здесь только её размер.
    const { data } = await api.post('/payments/pay/', {
      amount: Number(payAmount.value),
    })
    if (data.confirmation_url) {
      // Уходим на форму провайдера; вернёмся на /dashboard?payment=<id>
      window.location.href = data.confirmation_url
      return
    }
    $q.notify({ type: 'warning', message: 'Провайдер не вернул ссылку на оплату' })
  } catch (e) {
    $q.notify({
      type: 'negative',
      message: e.response?.data?.detail || 'Не удалось начать оплату',
    })
  } finally {
    paying.value = false
    payDialog.value = false
  }
}

async function checkReturnedPayment() {
  const intentId = route.query.payment
  if (!intentId) return
  try {
    const { data } = await api.get(`/payments/intents/${intentId}/`)
    if (data.status === 'succeeded') {
      payResult.value = { ok: true, text: `Оплата ${data.amount} ₽ прошла. Спасибо!` }
    } else if (data.status === 'pending') {
      // Провайдер мог ещё не прислать уведомление — это нормально,
      // деньги подтверждаются вебхуком, а не возвратом на страницу.
      payResult.value = {
        ok: false,
        text: 'Платёж обрабатывается. Задолженность обновится, когда банк подтвердит оплату.',
      }
    } else {
      payResult.value = {
        ok: false,
        text: data.error_message || 'Платёж не завершён.',
      }
    }
  } catch (e) {
    console.error(e)
  }
}

onMounted(async () => {
  if (auth.isMember) {
    await checkReturnedPayment()
    await loadMyDebt()
  }
  if (!auth.isMember) {
    try {
      const [members, plots] = await Promise.all([
        api.get('/members/?page_size=1'),
        api.get('/plots/?page_size=1'),
      ])
      stats.value.members = members.data.count || 0
      stats.value.plots = plots.data.count || 0

      // Долги — через открытый период
      const periods = await api.get('/billing/periods/?status=open&page_size=1')
      if (periods.data.results?.length) {
        const pid = periods.data.results[0].id
        const debt = await api.get(`/billing/periods/${pid}/debt_summary/`)
        const debtors = debt.data.filter((d) => d.debt > 0)
        stats.value.debtors = debtors.length
        stats.value.totalDebt = debtors.reduce((s, d) => s + Number(d.debt), 0)
      }
    } catch (e) {
      console.error(e)
    }
  }
})
</script>
