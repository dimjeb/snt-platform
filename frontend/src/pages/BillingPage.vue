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
        </div>

        <q-list separator bordered rounded>
          <q-item v-for="d in debtSummary" :key="d.plot_id">
            <q-item-section>
              <q-item-label>Уч. №{{ d.plot_number }} — {{ d.member_name }}</q-item-label>
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
        <q-list separator bordered rounded>
          <q-item v-for="c in charges" :key="c.id">
            <q-item-section>
              <q-item-label>{{ c.charge_type_name }}</q-item-label>
              <q-item-label caption>Уч. №{{ c.plot_number }} · {{ c.description }}</q-item-label>
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
    <q-dialog v-model="bulkMembershipDialog" persistent>
      <q-card style="min-width:320px">
        <q-card-section class="text-h6">Начислить членские взносы</q-card-section>
        <q-card-section>
          <q-form class="q-gutter-sm">
            <q-input v-model="membershipForm.amount" label="Сумма (₽) *" outlined dense type="number" />
            <q-input v-model="membershipForm.description" label="Описание" outlined dense />
          </q-form>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="green-8" label="Начислить всем" :loading="actionLoading" @click="createMembership" />
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
import { ref, onMounted } from 'vue'
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
const actionLoading = ref(false)
const bulkMembershipDialog = ref(false)
const bulkTargetDialog = ref(false)
const paymentDialog = ref(false)
const membershipForm = ref({ amount: '', description: '' })
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

async function loadPeriods() {
  const { data } = await api.get('/billing/periods/?page_size=24&ordering=-year,-month')
  periods.value = data.results.map((p) => ({ ...p, label: `${p.year}-${String(p.month).padStart(2, '0')} (${p.status})` }))
  if (periods.value.length) {
    selectedPeriod.value = periods.value[0].id
    await onPeriodChange(selectedPeriod.value)
  }
}

async function onPeriodChange(pid) {
  if (!pid) return
  const [debt, ch, pay] = await Promise.all([
    api.get(`/billing/periods/${pid}/debt_summary/`),
    api.get(`/billing/charges/?period=${pid}&page_size=100`),
    api.get(`/billing/payments/?period=${pid}&page_size=100`),
  ])
  debtSummary.value = debt.data
  charges.value = ch.data.results || ch.data
  payments.value = pay.data.results || pay.data
  chargeOptions.value = (ch.data.results || ch.data).map((c) => ({
    label: `Уч.${c.plot_number} ${c.charge_type_name} ${formatMoney(c.amount)}₽`,
    value: c.id,
  }))
}

async function createMembership() {
  actionLoading.value = true
  try {
    await api.post(`/billing/periods/${selectedPeriod.value}/create_membership_charges/`, membershipForm.value)
    bulkMembershipDialog.value = false
    await onPeriodChange(selectedPeriod.value)
    $q.notify({ type: 'positive', message: 'Взносы начислены' })
  } catch { $q.notify({ type: 'negative', message: 'Ошибка' }) }
  finally { actionLoading.value = false }
}

async function createPayment() {
  actionLoading.value = true
  try {
    await api.post('/billing/payments/', payForm.value)
    paymentDialog.value = false
    await onPeriodChange(selectedPeriod.value)
    $q.notify({ type: 'positive', message: 'Платёж внесён' })
  } catch { $q.notify({ type: 'negative', message: 'Ошибка' }) }
  finally { actionLoading.value = false }
}

onMounted(loadPeriods)
</script>
