<template>
  <q-page class="q-pa-md">
    <div class="text-h6 q-mb-md">Отчёты</div>

    <!-- Выбор периода -->
    <q-select
      v-model="selectedPeriod"
      :options="periods"
      option-label="label"
      option-value="id"
      emit-value map-options
      label="Период"
      outlined dense
      class="q-mb-lg"
    />

    <div class="q-gutter-md">
      <!-- Реестр должников -->
      <q-card flat bordered>
        <q-card-section>
          <div class="row items-center">
            <div class="col">
              <div class="text-subtitle1">📊 Реестр должников</div>
              <div class="text-caption text-grey-7">Сводный Excel с суммами долгов по участкам</div>
            </div>
            <div>
              <q-btn flat icon="download" color="green-8" :loading="downloading.debt" @click="downloadReport('debt')" />
              <q-btn flat icon="email" color="blue-8" :loading="emailing.debt" @click="emailReport('debt')" />
            </div>
          </div>
        </q-card-section>
      </q-card>

      <!-- Квитанции -->
      <q-card flat bordered>
        <q-card-section>
          <div class="row items-center">
            <div class="col">
              <div class="text-subtitle1">🧾 Квитанции</div>
              <div class="text-caption text-grey-7">Список платежей за период</div>
            </div>
            <div>
              <q-btn flat icon="download" color="green-8" :loading="downloading.receipts" @click="downloadReport('receipts')" />
              <q-btn flat icon="email" color="blue-8" :loading="emailing.receipts" @click="emailReport('receipts')" />
            </div>
          </div>
        </q-card-section>
      </q-card>

      <!-- Реестр членов -->
      <q-card flat bordered>
        <q-card-section>
          <div class="row items-center">
            <div class="col">
              <div class="text-subtitle1">👥 Реестр членов</div>
              <div class="text-caption text-grey-7">Список членов СНТ с участками</div>
            </div>
            <div>
              <q-btn flat icon="download" color="green-8" :loading="downloading.members" @click="downloadReport('members')" />
              <q-btn flat icon="email" color="blue-8" :loading="emailing.members" @click="emailReport('members')" />
            </div>
          </div>
        </q-card-section>
      </q-card>
    </div>

    <!-- Email диалог -->
    <q-dialog v-model="emailDialog" persistent>
      <q-card style="min-width:320px">
        <q-card-section class="text-h6">Отправить отчёт на email</q-card-section>
        <q-card-section>
          <q-input v-model="emailTo" label="Email получателя *" outlined dense type="email" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="green-8" label="Отправить" :loading="sendingEmail" @click="sendEmail" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- История отчётов -->
    <div class="q-mt-lg" v-if="reports.length">
      <div class="text-subtitle2 q-mb-sm">Ранее сформированные отчёты</div>
      <q-list separator bordered rounded dense>
        <q-item v-for="r in reports" :key="r.id">
          <q-item-section>
            <q-item-label>{{ reportTypeLabel(r.report_type) }}</q-item-label>
            <q-item-label caption>{{ r.created_at?.slice(0,10) }} · {{ r.generated_by_name }}</q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-btn flat icon="download" size="sm" :href="r.file" target="_blank" />
          </q-item-section>
        </q-item>
      </q-list>
    </div>
  </q-page>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import api from 'src/api/client'

const $q = useQuasar()
const periods = ref([])
const selectedPeriod = ref(null)
const reports = ref([])
const emailDialog = ref(false)
const emailTo = ref('')
const sendingEmail = ref(false)
const pendingEmailType = ref('')
const downloading = ref({ debt: false, receipts: false, members: false })
const emailing = ref({ debt: false, receipts: false, members: false })

const typeMap = { debt: 'Реестр должников', receipts: 'Квитанции', members: 'Реестр членов' }
function reportTypeLabel(t) { return typeMap[t] || t }

const reportEndpoints = {
  debt: '/reports/debt/',
  receipts: '/reports/receipts/',
  members: '/reports/members/',
}

async function downloadReport(type) {
  if (!selectedPeriod.value && type !== 'members') {
    $q.notify({ type: 'warning', message: 'Выберите период' }); return
  }
  downloading.value[type] = true
  try {
    const params = {}
    if (type !== 'members') params.period_id = selectedPeriod.value
    const { data, headers } = await api.get(reportEndpoints[type], {
      params,
      responseType: 'blob',
    })
    const url = URL.createObjectURL(new Blob([data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `${typeMap[type]}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch { $q.notify({ type: 'negative', message: 'Ошибка формирования отчёта' }) }
  finally { downloading.value[type] = false }
}

function emailReport(type) {
  pendingEmailType.value = type
  emailTo.value = ''
  emailDialog.value = true
}

async function sendEmail() {
  if (!emailTo.value) return
  sendingEmail.value = true
  const type = pendingEmailType.value
  try {
    const payload = { email: emailTo.value }
    if (type !== 'members') payload.period_id = selectedPeriod.value
    await api.post(reportEndpoints[type], payload)
    emailDialog.value = false
    $q.notify({ type: 'positive', message: `Отчёт отправлен на ${emailTo.value}` })
  } catch { $q.notify({ type: 'negative', message: 'Ошибка отправки' }) }
  finally { sendingEmail.value = false }
}

async function loadPeriods() {
  const { data } = await api.get('/billing/periods/?page_size=24&ordering=-year,-month')
  periods.value = data.results.map((p) => ({
    ...p,
    label: `${p.year}-${String(p.month).padStart(2, '0')}`,
  }))
  if (periods.value.length) selectedPeriod.value = periods.value[0].id
}

async function loadReports() {
  try {
    const { data } = await api.get('/reports/?page_size=20&ordering=-created_at')
    reports.value = data.results || data
  } catch { /* no reports endpoint yet */ }
}

onMounted(() => { loadPeriods(); loadReports() })
</script>
