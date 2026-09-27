<template>
  <!-- Обычный div, а не q-page. Маршрут /change-password объявлен вне
       MainLayout (пока пароль временный, меню разделов показывать
       бессмысленно), а QPage без QLayout над собой молча возвращает
       пустой рендер — страница выходила белой, и в консоли была лишь
       строчка «QPage needs to be a deep child of QLayout». LoginPage
       живёт вне layout по той же причине и тоже обходится div. -->
  <div class="change-password-page">
    <div class="change-password-card">
      <q-card flat bordered>
        <q-card-section class="bg-green-8 text-white">
          <div class="row items-center no-wrap">
            <q-icon name="lock_reset" size="32px" class="q-mr-md" />
            <div>
              <div class="text-h6">Смена пароля</div>
              <div class="text-caption">
                {{ forced ? 'Это нужно сделать один раз, при первом входе' : 'Придумайте новый пароль' }}
              </div>
            </div>
          </div>
        </q-card-section>

        <q-card-section v-if="forced" class="bg-orange-1 text-orange-10 text-body2">
          <q-icon name="info" class="q-mr-xs" />
          Вам выдали временный пароль. Пока он не заменён на собственный,
          остальные разделы закрыты.
        </q-card-section>

        <q-card-section class="q-gutter-md">
          <q-input
            v-model="oldPassword"
            :label="forced ? 'Временный пароль *' : 'Текущий пароль *'"
            outlined
            :type="showOld ? 'text' : 'password'"
            autocomplete="current-password"
            :error="!!fieldErrors.old_password"
            :error-message="fieldErrors.old_password"
          >
            <template #prepend><q-icon name="lock_open" /></template>
            <template #append>
              <q-icon
                :name="showOld ? 'visibility_off' : 'visibility'"
                class="cursor-pointer"
                @click="showOld = !showOld"
              />
            </template>
          </q-input>

          <q-input
            v-model="newPassword"
            label="Новый пароль *"
            outlined
            :type="showNew ? 'text' : 'password'"
            autocomplete="new-password"
            :error="!!fieldErrors.new_password"
            :error-message="fieldErrors.new_password"
            hint="Не менее 10 символов, не только цифры, не словарное слово"
          >
            <template #prepend><q-icon name="lock" /></template>
            <template #append>
              <q-icon
                :name="showNew ? 'visibility_off' : 'visibility'"
                class="cursor-pointer"
                @click="showNew = !showNew"
              />
            </template>
          </q-input>

          <q-input
            v-model="repeatPassword"
            label="Новый пароль ещё раз *"
            outlined
            :type="showNew ? 'text' : 'password'"
            autocomplete="new-password"
            :error="mismatch"
            error-message="Пароли не совпадают"
          >
            <template #prepend><q-icon name="lock" /></template>
          </q-input>

          <div v-if="generalError" class="text-negative text-body2">
            {{ generalError }}
          </div>
        </q-card-section>

        <q-card-actions align="right" class="q-pa-md q-pt-none">
          <q-btn
            v-if="!forced"
            flat
            label="Отмена"
            @click="$router.back()"
          />
          <q-btn
            color="green-8"
            label="Сохранить"
            unelevated
            :loading="saving"
            :disable="!canSubmit"
            @click="submit"
          />
        </q-card-actions>
      </q-card>

      <div v-if="forced" class="text-center q-mt-md">
        <q-btn flat dense size="sm" color="grey-7" label="Выйти" @click="logout" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import api from 'src/api/client'
import { useAuthStore } from 'stores/auth'

const $q = useQuasar()
const router = useRouter()
const auth = useAuthStore()

const oldPassword = ref('')
const newPassword = ref('')
const repeatPassword = ref('')
const showOld = ref(false)
const showNew = ref(false)
const saving = ref(false)
const generalError = ref('')
const fieldErrors = ref({})

const forced = computed(() => !!auth.user?.must_change_password)
const mismatch = computed(
  () => !!repeatPassword.value && newPassword.value !== repeatPassword.value,
)
const canSubmit = computed(
  () => oldPassword.value && newPassword.value && !mismatch.value,
)

async function submit() {
  saving.value = true
  generalError.value = ''
  fieldErrors.value = {}
  try {
    await api.post('/auth/change-password/', {
      old_password: oldPassword.value,
      new_password: newPassword.value,
    })
    // Флаг снят на сервере — перечитываем профиль, иначе навигационный
    // сторож продолжит возвращать сюда же.
    await auth.fetchMe()
    $q.notify({ type: 'positive', message: 'Пароль изменён' })
    await router.replace('/dashboard')
  } catch (e) {
    const data = e.response?.data
    if (data && typeof data === 'object') {
      const errs = {}
      for (const key of ['old_password', 'new_password']) {
        if (data[key]) errs[key] = [].concat(data[key]).join(' ')
      }
      fieldErrors.value = errs
      if (!Object.keys(errs).length) {
        generalError.value = [].concat(data.detail || JSON.stringify(data)).join(' ')
      }
    } else {
      generalError.value = 'Не удалось сменить пароль. Попробуйте ещё раз.'
    }
  } finally {
    saving.value = false
  }
}

function logout() {
  auth.logout()
  router.replace('/login')
}
</script>

<style scoped>
.change-password-page {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  /* Высоту давал QPage; без него её надо задать самим, иначе карточка
     прилипает к верхнему краю. */
  min-height: 100vh;
}
.change-password-card {
  width: 100%;
  max-width: 440px;
}
</style>
