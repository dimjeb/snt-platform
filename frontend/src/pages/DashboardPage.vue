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

      <q-card flat bordered class="q-mb-md" v-if="myDebts.length">
        <q-card-section>
          <div class="text-subtitle2 q-mb-sm">Мои задолженности</div>
          <q-list separator dense>
            <q-item v-for="d in myDebts" :key="d.id">
              <q-item-section>{{ d.charge_type_name }} · {{ d.period_name }}</q-item-section>
              <q-item-section side class="debt-amount">{{ formatMoney(d.debt) }} ₽</q-item-section>
            </q-item>
          </q-list>
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
import { ref, onMounted } from 'vue'
import { useAuthStore } from 'stores/auth'
import api from 'src/api/client'

const auth = useAuthStore()

const stats = ref({ members: 0, plots: 0, debtors: 0, totalDebt: 0 })
const myDebts = ref([])

function formatMoney(val) {
  if (!val) return '0'
  return Number(val).toLocaleString('ru-RU', { maximumFractionDigits: 0 })
}

onMounted(async () => {
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
