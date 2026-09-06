<template>
  <q-page class="flex flex-center bg-grey-2">
    <q-card class="login-card shadow-4">
      <q-card-section class="bg-green-8 text-white text-center q-py-lg">
        <q-icon name="park" size="48px" />
        <div class="text-h5 q-mt-sm">СНТ Платформа</div>
        <div class="text-caption">Управление садоводческим товариществом</div>
      </q-card-section>

      <q-card-section class="q-pa-lg">
        <q-form @submit.prevent="onLogin" class="q-gutter-md">
          <q-input
            v-model="username"
            label="Логин"
            outlined
            autofocus
            :rules="[(v) => !!v || 'Введите логин']"
          >
            <template #prepend><q-icon name="person" /></template>
          </q-input>

          <q-input
            v-model="password"
            label="Пароль"
            outlined
            :type="showPass ? 'text' : 'password'"
            :rules="[(v) => !!v || 'Введите пароль']"
          >
            <template #prepend><q-icon name="lock" /></template>
            <template #append>
              <q-icon
                :name="showPass ? 'visibility_off' : 'visibility'"
                class="cursor-pointer"
                @click="showPass = !showPass"
              />
            </template>
          </q-input>

          <div v-if="errorMsg" class="text-negative text-caption">{{ errorMsg }}</div>

          <q-btn
            type="submit"
            color="green-8"
            label="Войти"
            class="full-width q-py-sm"
            :loading="loading"
            unelevated
          />
        </q-form>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from 'stores/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const showPass = ref(false)
const loading = ref(false)
const errorMsg = ref('')

async function onLogin() {
  errorMsg.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    await router.push('/dashboard')
  } catch (e) {
    const status = e.response?.status
    if (status === 401) {
      errorMsg.value = 'Неверный логин или пароль'
    } else {
      errorMsg.value = 'Ошибка сервера. Попробуйте позже.'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-card {
  width: 100%;
  max-width: 400px;
}
</style>
