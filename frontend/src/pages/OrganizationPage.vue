<template>
  <q-page padding>
    <div class="text-h6 q-mb-md">Товарищество</div>

    <q-card flat bordered style="max-width:560px">
      <q-card-section>
        <div class="text-subtitle1 text-weight-medium">Логотип</div>
        <div class="text-caption text-grey-7">
          Показывается в меню слева, над именем пользователя, у всех членов товарищества.
          PNG, JPG или WEBP, до 2 МБ. Лучше всего — квадратный или
          вытянутый по ширине, на белом или прозрачном фоне.
        </div>
      </q-card-section>

      <q-card-section class="row items-center q-gutter-md">
        <div class="org-logo-preview flex flex-center">
          <img v-if="logo" :src="logo" alt="Логотип" class="org-logo-img" />
          <div v-else class="text-grey-6 text-caption text-center">Логотипа<br>пока нет</div>
        </div>
        <div class="col">
          <q-file
            v-model="file"
            label="Выбрать картинку"
            outlined dense
            accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
            max-file-size="2097152"
            @rejected="onRejected"
          >
            <template #prepend><q-icon name="image" /></template>
          </q-file>
          <div class="row q-gutter-sm q-mt-sm">
            <q-btn color="primary" icon="upload" label="Загрузить" :disable="!file"
                   :loading="saving" @click="upload" />
            <q-btn v-if="logo" flat color="negative" icon="delete" label="Убрать логотип"
                   :loading="removing" @click="remove" />
          </div>
        </div>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import api from 'src/api/client'
import { useAuthStore } from 'src/stores/auth'

const $q = useQuasar()
const auth = useAuthStore()
const file = ref(null)
const saving = ref(false)
const removing = ref(false)
const logo = computed(() => auth.orgInfo?.logo || null)

function errorText(e) {
  const d = e.response?.data
  if (d && typeof d === 'object') return Object.values(d).flat().join(' ')
  return 'Не получилось'
}

function onRejected() {
  $q.notify({ type: 'warning', message: 'Нужна картинка PNG, JPG или WEBP до 2 МБ' })
}

async function load() {
  try {
    const { data } = await api.get('/organizations/current/')
    auth.setOrgInfo(data)
  } catch (e) {
    $q.notify({ type: 'negative', message: errorText(e) })
  }
}

async function upload() {
  saving.value = true
  try {
    const form = new FormData()
    form.append('logo', file.value)
    const { data } = await api.post('/organizations/current/logo/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    auth.setOrgInfo(data)
    file.value = null
    $q.notify({ type: 'positive', message: 'Логотип загружен' })
  } catch (e) {
    $q.notify({ type: 'negative', message: errorText(e) })
  } finally {
    saving.value = false
  }
}

function remove() {
  $q.dialog({
    title: 'Убрать логотип?',
    message: 'Из меню логотип пропадёт, пока не загрузите новый.',
    cancel: true,
  }).onOk(async () => {
    removing.value = true
    try {
      await api.delete('/organizations/current/logo/')
      auth.setOrgInfo({ ...auth.orgInfo, logo: null })
      $q.notify({ type: 'positive', message: 'Логотип убран' })
    } catch (e) {
      $q.notify({ type: 'negative', message: errorText(e) })
    } finally {
      removing.value = false
    }
  })
}

onMounted(load)
</script>

<style scoped>
.org-logo-preview {
  width: 140px;
  height: 140px;
  border: 1px dashed #bbb;
  border-radius: 8px;
  background: #fff;
}
.org-logo-img {
  max-width: 128px;
  max-height: 128px;
  object-fit: contain;
}
</style>
