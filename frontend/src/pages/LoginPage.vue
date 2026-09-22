<template>
  <div class="login-page">
    <!-- Левая панель — брендинг (только десктоп) -->
    <div class="login-left gt-sm">
      <div class="login-left-content">
        <div class="login-brand-icon">
          <q-icon name="park" size="52px" color="white" />
        </div>
        <h1 class="login-brand-title">СНТ Платформа</h1>
        <p class="login-brand-sub">Управление садоводческим товариществом</p>

        <div class="login-features">
          <div class="login-feature" v-for="f in features" :key="f.icon">
            <q-icon :name="f.icon" size="18px" style="opacity:0.8;flex-shrink:0" />
            <span>{{ f.text }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Правая панель — форма -->
    <div class="login-right">
      <!-- Мобильный логотип -->
      <div class="login-mobile-header lt-md">
        <q-icon name="park" size="36px" color="green-8" />
        <div class="text-h6 text-green-8 q-mt-xs">СНТ Платформа</div>
        <div class="text-caption text-grey-6">Управление садоводческим товариществом</div>
      </div>

      <q-card class="login-card" flat>
        <q-card-section class="q-pb-none q-pt-md">
          <div class="text-h6 gt-sm">Вход в систему</div>
          <div class="text-caption text-grey-6 gt-sm q-mb-md">Введите ваши учётные данные</div>
        </q-card-section>

        <q-card-section class="q-pt-sm">
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

        <q-card-section class="text-center q-pt-sm">
          <div class="text-caption text-grey-5">
            Забыли пароль? Обратитесь к председателю СНТ
          </div>
        </q-card-section>
      </q-card>
    </div>
  </div>
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

const features = [
  { icon: 'people',       text: 'Учёт членов и участков' },
  { icon: 'receipt_long', text: 'Начисления и платежи' },
  { icon: 'bolt',         text: 'Учёт электроэнергии' },
  { icon: 'bar_chart',    text: 'Отчёты в Excel' },
]

// Одно «Ошибка сервера. Попробуйте позже.» на все случаи, кроме 401,
// скрывало и код ответа, и текст с сервера: по экрану нельзя было
// отличить упавший бэкенд от недоступного сервера или от требования
// сменить пароль. Разбираться приходилось по логам контейнера.
function loginError(e) {
  const status = e?.response?.status
  const data = e?.response?.data

  if (status === 401) return 'Неверный логин или пароль'
  if (status === 403 && data?.must_change_password) {
    return 'Нужно сменить временный пароль'
  }
  if (!e?.response) {
    return 'Сервер не отвечает. Проверьте связь и попробуйте ещё раз.'
  }
  const detail = typeof data?.detail === 'string' ? data.detail : ''
  return `Ошибка ${status}${detail ? ': ' + detail : ''}`
}

async function onLogin() {
  errorMsg.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
  } catch (e) {
    // Код ответа в консоль: он нужен, когда человек присылает скриншот.
    console.error('Вход не удался:', e?.response?.status, e?.response?.data)
    errorMsg.value = loginError(e)
    loading.value = false
    return
  }

  // Навигация — отдельно от входа. Раньше она стояла в том же try, и
  // осечка перехода (например, редирект на смену пароля, отменяющий
  // текущий переход) показывалась как «Ошибка сервера», хотя вход
  // прошёл и токен уже получен.
  try {
    await router.push(auth.user?.must_change_password ? '/change-password' : '/dashboard')
  } catch (e) {
    console.error('Переход после входа не удался:', e)
    window.location.assign(
      auth.user?.must_change_password ? '/change-password' : '/dashboard'
    )
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  min-height: 100vh;
}

/* Левая панель */
.login-left {
  flex: 1;
  background: linear-gradient(160deg, #2d6a4f 0%, #1b4332 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 40px;
  position: relative;
  overflow: hidden;
}
.login-left::before {
  content: '';
  position: absolute;
  width: 340px; height: 340px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.07);
  top: -80px; right: -80px;
}
.login-left::after {
  content: '';
  position: absolute;
  width: 220px; height: 220px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.07);
  bottom: 40px; left: -60px;
}
.login-left-content { position: relative; z-index: 1; max-width: 360px; }

.login-brand-icon {
  width: 80px; height: 80px;
  background: rgba(255,255,255,0.12);
  border-radius: 20px;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 24px;
}
.login-brand-title {
  color: white;
  font-size: 1.9rem;
  font-weight: 700;
  margin: 0 0 8px;
  line-height: 1.2;
}
.login-brand-sub {
  color: rgba(255,255,255,0.65);
  font-size: 0.95rem;
  margin: 0 0 36px;
}

.login-features {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.login-feature {
  display: flex;
  align-items: center;
  gap: 12px;
  color: rgba(255,255,255,0.8);
  font-size: 0.9rem;
}

/* Правая панель */
.login-right {
  width: 420px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 32px;
  background: var(--q-color-grey-1, #fafafa);
}
.login-card {
  width: 100%;
  max-width: 360px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 20px rgba(0,0,0,0.08);
}

.login-mobile-header {
  text-align: center;
  margin-bottom: 24px;
}

/* Мобиль: одна колонка */
@media (max-width: 768px) {
  .login-page { justify-content: center; align-items: center; background: #f5f5f5; }
  .login-right {
    width: 100%;
    padding: 24px 16px;
  }
  .login-card {
    max-width: 400px;
  }
}

/* Тёмная тема */
.body--dark .login-right { background: #1a1a1a; }
.body--dark .login-card  { background: #2a2a2a !important; box-shadow: 0 2px 20px rgba(0,0,0,0.4); }
</style>
