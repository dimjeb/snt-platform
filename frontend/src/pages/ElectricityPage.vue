<template>
  <q-page class="q-pa-md">
    <div class="text-h6 q-mb-md">Электроэнергия</div>

    <q-tabs v-model="tab" dense align="left" class="q-mb-md" active-color="orange-8" indicator-color="orange-8">
      <q-tab name="meters" label="Счётчики" />
      <q-tab name="readings" label="Показания" />
      <q-tab name="tariffs" label="Тарифы" />
    </q-tabs>

    <q-tab-panels v-model="tab" animated>
      <!-- Счётчики -->
      <q-tab-panel name="meters" class="q-pa-none">
        <q-btn outline color="orange-8" icon="add" label="Добавить счётчик" class="q-mb-md" @click="openNewMeter" />
        <q-list separator bordered rounded>
          <q-item v-for="m in meters" :key="m.id">
            <q-item-section avatar>
              <q-icon :name="m.is_main ? 'electric_meter' : 'speed'" :color="m.is_main ? 'orange-8' : 'grey-7'" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ m.is_main ? '[ГЛАВНЫЙ] ' : '' }}{{ m.serial_number }}</q-item-label>
              <q-item-label caption>Участок: {{ m.plot_number || '—' }}</q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-btn flat dense no-caps color="orange-8" icon="edit_note" label="Показание и долг" @click="openOpening(m)" />
            </q-item-section>
          </q-item>
          <q-item v-if="!meters.length"><q-item-section class="text-center text-grey-6">Нет счётчиков</q-item-section></q-item>
        </q-list>
      </q-tab-panel>

      <!-- Показания -->
      <q-tab-panel name="readings" class="q-pa-none">
        <div class="row q-gutter-sm q-mb-md">
          <q-input v-model="readingMonth" type="month" outlined dense label="Период" class="col" />
          <q-btn
            color="orange-8" icon="calculate" label="Рассчитать"
            :loading="calculating"
            @click="calculate"
          />
        </div>

        <q-list separator bordered rounded>
          <q-item v-for="r in readings" :key="r.id">
            <q-item-section>
              <q-item-label>Сч. {{ r.meter_serial }} · Уч. {{ r.plot_number || '—' }}</q-item-label>
              <q-item-label caption>{{ r.date }}: {{ r.value }} кВт·ч{{ r.value_night ? ' / ' + r.value_night + ' (ночь)' : '' }}</q-item-label>
            </q-item-section>
          </q-item>
          <q-item v-if="!readings.length"><q-item-section class="text-center text-grey-6">Нет показаний</q-item-section></q-item>
        </q-list>
      </q-tab-panel>

      <!-- Тарифы -->
      <q-tab-panel name="tariffs" class="q-pa-none">
        <q-btn outline color="orange-8" icon="add" label="Добавить тариф" class="q-mb-md" @click="tariffDialog = true" />
        <q-list separator bordered rounded>
          <q-item v-for="t in tariffs" :key="t.id">
            <q-item-section>
              <q-item-label>С {{ t.valid_from }}</q-item-label>
              <q-item-label caption>{{ t.price_per_kwh }} ₽/кВт·ч{{ t.price_per_kwh_night ? ' (день) / ' + t.price_per_kwh_night + ' (ночь)' : '' }}</q-item-label>
            </q-item-section>
          </q-item>
          <q-item v-if="!tariffs.length"><q-item-section class="text-center text-grey-6">Нет тарифов</q-item-section></q-item>
        </q-list>
      </q-tab-panel>
    </q-tab-panels>

    <!-- Диалог: счётчик -->
    <q-dialog v-model="meterDialog" persistent>
      <q-card style="min-width:300px">
        <q-card-section class="text-h6">
          {{ openingFor ? `Счётчик ${openingFor.serial_number}: показание и долг` : 'Новый счётчик' }}
        </q-card-section>
        <q-card-section>
          <q-form class="q-gutter-sm">
            <template v-if="!openingFor">
            <q-input v-model="meterForm.serial_number" label="Серийный номер *" outlined dense />
            <q-select
              v-model="meterForm.plot"
              label="Участок"
              outlined dense
              :options="plotOptions"
              emit-value map-options
              clearable
            />
            <q-toggle v-model="meterForm.is_main" label="Главный счётчик (общий)" />
            </template>
            <div class="text-subtitle2 q-mt-md">Что на счётчике сейчас</div>
            <div class="text-caption text-grey-7">
              От этого показания пойдёт первый расчёт: до этой даты свет не начисляется.
            </div>
            <q-input v-model="meterForm.initial_date" label="Дата показания" outlined dense type="date" />
            <q-input v-model="meterForm.initial_reading" label="Показание, кВт·ч" outlined dense type="number" step="0.001" min="0"
                     hint="Всё число со счётчика целиком" />
            <q-input v-model="meterForm.initial_reading_night" label="Ночное показание (двухтарифный)" outlined dense type="number" step="0.001" min="0" />
            <template v-if="!debtTarget.isMain">
              <q-input v-model="meterForm.opening_debt" label="Долг за свет на эту дату, ₽" outlined dense type="number" step="0.01" min="0"
                       :disable="!debtTarget.plot"
                       :hint="debtTarget.plot ? 'Ляжет начислением «Электроэнергия» на участок' : 'Сначала выберите участок'" />
            </template>
          </q-form>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="orange-8" label="Сохранить" :loading="saving" @click="saveMeter" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Диалог: тариф -->
    <q-dialog v-model="tariffDialog" persistent>
      <q-card style="min-width:300px">
        <q-card-section class="text-h6">Новый тариф</q-card-section>
        <q-card-section>
          <q-form class="q-gutter-sm">
            <q-input v-model="tariffForm.valid_from" label="Действует с *" outlined dense type="date" />
            <q-input v-model="tariffForm.price_per_kwh" label="Тариф день (₽/кВт·ч) *" outlined dense type="number" step="0.01" />
            <q-input v-model="tariffForm.price_per_kwh_night" label="Тариф ночь (₽/кВт·ч)" outlined dense type="number" step="0.01" />
          </q-form>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Отмена" v-close-popup />
          <q-btn color="orange-8" label="Сохранить" :loading="saving" @click="saveTariff" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import api from 'src/api/client'

const $q = useQuasar()
const tab = ref('meters')
const meters = ref([])
const readings = ref([])
const tariffs = ref([])
const plotOptions = ref([])
const meterDialog = ref(false)
const tariffDialog = ref(false)
const saving = ref(false)
const calculating = ref(false)
const readingMonth = ref(new Date().toISOString().slice(0, 7))
const emptyMeterForm = () => ({
  serial_number: '', plot: null, is_main: false,
  initial_date: new Date().toISOString().slice(0, 10),
  initial_reading: '', initial_reading_night: '', opening_debt: '',
})
const meterForm = ref(emptyMeterForm())
// Счётчик, которому вносим показание и долг; null — заводим новый.
const openingFor = ref(null)
const debtTarget = computed(() => (openingFor.value
  ? { isMain: openingFor.value.is_main, plot: openingFor.value.plot }
  : { isMain: meterForm.value.is_main, plot: meterForm.value.plot }))

function openNewMeter() {
  openingFor.value = null
  meterForm.value = emptyMeterForm()
  meterDialog.value = true
}

function openOpening(m) {
  openingFor.value = m
  meterForm.value = emptyMeterForm()
  meterDialog.value = true
}
const tariffForm = ref({ valid_from: '', price_per_kwh: '', price_per_kwh_night: '' })

async function load() {
  const [m, t, pl] = await Promise.all([
    api.get('/electricity/meters/?page_size=100'),
    api.get('/electricity/tariffs/?page_size=20'),
    api.get('/plots/?page_size=200'),
  ])
  meters.value = m.data.results || m.data
  tariffs.value = t.data.results || t.data
  plotOptions.value = (pl.data.results || pl.data).map((p) => ({ label: `№${p.number}`, value: p.id }))
  await loadReadings()
}

async function loadReadings() {
  const [year, month] = readingMonth.value.split('-')
  const { data } = await api.get('/electricity/readings/', { params: { year, month, page_size: 200 } })
  readings.value = data.results || data
}

async function calculate() {
  calculating.value = true
  try {
    const [year, month] = readingMonth.value.split('-')
    // Получаем период биллинга
    const periods = await api.get(`/billing/periods/?year=${year}&month=${month}&page_size=1`)
    if (!periods.data.results?.length) {
      $q.notify({ type: 'warning', message: 'Сначала создайте период биллинга' })
      return
    }
    const pid = periods.data.results[0].id
    // Запускаем расчёт через action счётчика
    const mainMeter = meters.value.find((m) => m.is_main)
    if (!mainMeter) { $q.notify({ type: 'warning', message: 'Не найден главный счётчик' }); return }
    // Последний день месяца, а не первый: от этой даты зависит выбор
    // тарифа, и тариф, вступивший в силу в середине месяца, с первым
    // числом просто не нашёлся бы.
    const lastDay = new Date(Number(year), Number(month), 0).getDate()
    // action объявлен detail=False, поэтому маршрут без id счётчика
    const { data } = await api.post('/electricity/meters/calculate/', {
      billing_period_id: pid,
      period_date: `${year}-${month}-${String(lastDay).padStart(2, '0')}`,
    })
    // Сколько участков посчитано по среднему — это надо видеть: за них
    // начислено по оценке, и с ними придётся разбираться отдельно.
    const estimated = (data.details || []).filter((d) => d.missing_reading)
    if (estimated.length) {
      const plotList = estimated.map((d) => d.plot_number).join(', ')
      $q.notify({
        type: 'warning',
        timeout: 0,
        multiLine: true,
        actions: [{ label: 'Понятно', color: 'white' }],
        message: `Расчёт выполнен. Без показаний за период: ${estimated.length} `
          + `— начислено по среднему. Участки: ${plotList}`,
      })
    } else {
      $q.notify({ type: 'positive', message: 'Расчёт выполнен, начисления обновлены' })
    }
  } catch (e) {
    $q.notify({ type: 'negative', message: e.response?.data?.detail || 'Ошибка расчёта' })
  } finally {
    calculating.value = false
  }
}

async function saveMeter() {
  saving.value = true
  try {
    // Пустые поля не шлём: '' для числа сервер считает ошибкой.
    const f = meterForm.value
    const body = openingFor.value
      ? {}
      : { serial_number: f.serial_number, plot: f.plot, is_main: f.is_main }
    for (const k of ['initial_date', 'initial_reading', 'initial_reading_night']) {
      if (f[k] !== '' && f[k] !== null) body[k] = f[k]
    }
    if (!debtTarget.value.isMain && debtTarget.value.plot && Number(f.opening_debt) > 0) {
      body.opening_debt = f.opening_debt
    }
    const debtNote = body.opening_debt ? `, долг ${body.opening_debt} ₽ начислен` : ''
    if (openingFor.value) {
      await api.post(`/electricity/meters/${openingFor.value.id}/opening/`, body)
    } else {
      await api.post('/electricity/meters/', body)
    }
    const done = openingFor.value
      ? `Счётчик ${openingFor.value.serial_number}: записано${debtNote}`
      : `Счётчик добавлен${debtNote}`
    meterDialog.value = false
    meterForm.value = emptyMeterForm()
    openingFor.value = null
    await load()
    $q.notify({ type: 'positive', message: done })
  } catch (e) {
    const d = e.response?.data
    const msg = d && typeof d === 'object' ? Object.values(d).flat().join(' ') : ''
    $q.notify({ type: 'negative', message: msg || 'Ошибка' })
  }
  finally { saving.value = false }
}

async function saveTariff() {
  saving.value = true
  try {
    await api.post('/electricity/tariffs/', tariffForm.value)
    tariffDialog.value = false
    await load()
    $q.notify({ type: 'positive', message: 'Тариф добавлен' })
  } catch { $q.notify({ type: 'negative', message: 'Ошибка' }) }
  finally { saving.value = false }
}

onMounted(load)
</script>
