<template>
  <q-page class="q-pa-md">
    <div class="text-h6 q-mb-md">Показания счётчика</div>

    <q-card flat bordered class="q-mb-md" v-if="myMeter">
      <q-card-section>
        <div class="text-subtitle2">Мой счётчик: {{ myMeter.serial_number }}</div>
        <div class="text-caption text-grey-7">Участок №{{ myMeter.plot_number }}</div>
      </q-card-section>
    </q-card>

    <q-card flat bordered v-if="!myMeter && !loading" class="q-mb-md bg-orange-1">
      <q-card-section class="text-center text-grey-7">
        <q-icon name="warning" color="orange-8" size="32px" /><br />
        Счётчик не привязан к вашему участку.<br />Обратитесь к председателю.
      </q-card-section>
    </q-card>

    <q-form v-if="myMeter" @submit.prevent="submit" class="q-gutter-md">
      <q-input
        v-model="form.date"
        label="Дата снятия показаний *"
        outlined
        type="date"
        :rules="[(v) => !!v || 'Укажите дату']"
      />

      <q-input
        v-model="form.value"
        label="Показание (кВт·ч) *"
        outlined
        type="number"
        step="1"
        :rules="[(v) => !!v || 'Введите показание', (v) => v > 0 || 'Должно быть > 0']"
      >
        <template #prepend><q-icon name="speed" /></template>
      </q-input>

      <q-input
        v-if="myMeter.has_night_tariff"
        v-model="form.value_night"
        label="Ночное показание (кВт·ч)"
        outlined
        type="number"
        step="1"
      >
        <template #prepend><q-icon name="dark_mode" /></template>
      </q-input>

      <q-file
        v-model="photo"
        label="Фото счётчика (необязательно)"
        outlined
        accept="image/*"
        max-file-size="5000000"
      >
        <template #prepend><q-icon name="photo_camera" /></template>
      </q-file>

      <q-btn
        type="submit"
        color="orange-8"
        label="Передать показания"
        class="full-width"
        :loading="loading"
        unelevated
      />
    </q-form>

    <!-- История -->
    <div class="q-mt-lg" v-if="history.length">
      <div class="text-subtitle2 q-mb-sm">История передачи показаний</div>
      <q-list separator bordered rounded>
        <q-item v-for="r in history" :key="r.id">
          <q-item-section>
            <q-item-label>{{ r.date }}</q-item-label>
            <q-item-label caption>{{ r.value }} кВт·ч{{ r.value_night ? ' / ' + r.value_night + ' (ночь)' : '' }}</q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-icon v-if="r.photo" name="photo" color="grey-5" />
          </q-item-section>
        </q-item>
      </q-list>
    </div>
  </q-page>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import { useAuthStore } from 'stores/auth'
import api from 'src/api/client'

const $q = useQuasar()
const auth = useAuthStore()
const myMeter = ref(null)
const history = ref([])
const loading = ref(false)
const photo = ref(null)
const form = ref({
  date: new Date().toISOString().slice(0, 10),
  value: '',
  value_night: '',
})

async function load() {
  loading.value = true
  try {
    // Получаем участок текущего члена
    const me = auth.user
    if (!me?.member_id) return

    // Ищем счётчик, привязанный к участкам члена
    const plots = await api.get(`/plots/?member=${me.member_id}&page_size=10`)
    if (!plots.data.results?.length) return

    const plotId = plots.data.results[0].id
    const meters = await api.get(`/electricity/meters/?plot=${plotId}&page_size=1`)
    if (meters.data.results?.length) {
      myMeter.value = meters.data.results[0]
      const readings = await api.get(`/electricity/readings/?meter=${myMeter.value.id}&page_size=12&ordering=-date`)
      history.value = readings.data.results || readings.data
    }
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!myMeter.value) return
  loading.value = true
  try {
    const payload = new FormData()
    payload.append('meter', myMeter.value.id)
    payload.append('date', form.value.date)
    payload.append('value', form.value.value)
    if (form.value.value_night) payload.append('value_night', form.value.value_night)
    if (photo.value) payload.append('photo', photo.value)

    await api.post('/electricity/readings/', payload, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    $q.notify({ type: 'positive', message: 'Показания переданы!' })
    form.value.value = ''
    form.value.value_night = ''
    photo.value = null
    await load()
  } catch (e) {
    const msg = e.response?.data?.non_field_errors?.[0] || e.response?.data?.detail || 'Ошибка передачи'
    $q.notify({ type: 'negative', message: msg })
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
