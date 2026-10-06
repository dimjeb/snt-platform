<template>
  <q-page class="q-pa-md">
    <div class="text-h6 q-mb-xs">Новое садоводство</div>
    <div class="text-body2 text-grey-7 q-mb-md">
      Реквизиты, председатель и казначей — обязательно. Реестр, долги и счётчики можно загрузить
      сразу или позже, с соответствующих страниц.
    </div>

    <q-stepper v-model="step" vertical color="green-8" animated flat bordered class="wizard">
      <!-- 1. Товарищество -->
      <q-step :name="1" title="Товарищество" icon="home_work" :done="step > 1" :header-nav="!created">
        <div class="row q-col-gutter-sm">
          <q-input v-model="org.name" label="Название *" hint="Как в интерфейсе: СНТ «Ромашка»"
                   outlined dense class="col-12 col-sm-6" :error="!!errors.name" :error-message="errors.name" />
          <q-input v-model="org.full_name" label="Полное наименование (для платёжек)"
                   hint="Как в реквизитах счёта" outlined dense class="col-12 col-sm-6" />
          <q-input v-model="org.inn" label="ИНН" outlined dense maxlength="12" class="col-6 col-sm-4"
                   :error="!!errors.inn" :error-message="errors.inn" />
          <q-input v-model="org.kpp" label="КПП" outlined dense maxlength="9" class="col-6 col-sm-4"
                   :error="!!errors.kpp" :error-message="errors.kpp" />
          <q-input v-model="org.ogrn" label="ОГРН" outlined dense maxlength="13" class="col-12 col-sm-4" />
          <q-input v-model="org.legal_address" label="Юридический адрес" outlined dense class="col-12" />
          <q-input v-model="org.phone" label="Телефон" outlined dense class="col-12 col-sm-6" />
          <q-input v-model="org.email" label="Email" outlined dense class="col-12 col-sm-6"
                   :error="!!errors.email" :error-message="errors.email" />
        </div>
        <div class="text-subtitle2 q-mt-md">Банковские реквизиты — для QR-кода оплаты</div>
        <div class="row q-col-gutter-sm">
          <q-input v-model="org.bank_account" label="Расчётный счёт" outlined dense maxlength="20"
                   class="col-12 col-sm-6" :error="!!errors.bank_account" :error-message="errors.bank_account" />
          <q-input v-model="org.bank_bic" label="БИК" outlined dense maxlength="9" class="col-6 col-sm-3"
                   :error="!!errors.bank_bic" :error-message="errors.bank_bic" />
          <q-input v-model="org.bank_corr_account" label="Корр. счёт" outlined dense maxlength="20"
                   class="col-6 col-sm-3" :error="!!errors.bank_corr_account"
                   :error-message="errors.bank_corr_account" />
          <q-input v-model="org.bank_name" label="Банк" outlined dense class="col-12" />
        </div>
        <q-stepper-navigation>
          <q-btn color="green-8" label="Дальше" :disable="!org.name.trim()" @click="step = 2" />
        </q-stepper-navigation>
      </q-step>

      <!-- 2. Председатель и казначей -->
      <q-step :name="2" title="Председатель и казначей" icon="badge" :done="created" :header-nav="!created">
        <template v-if="!created">
          <div class="text-subtitle2">Председатель *</div>
          <div class="row q-col-gutter-sm q-mb-md">
            <q-input v-model="chairman.last_name" label="Фамилия *" outlined dense class="col-12 col-sm-4" />
            <q-input v-model="chairman.first_name" label="Имя *" outlined dense class="col-6 col-sm-4" />
            <q-input v-model="chairman.patronymic" label="Отчество" outlined dense class="col-6 col-sm-4" />
            <q-input v-model="chairman.phone" label="Телефон" outlined dense class="col-6" />
            <q-input v-model="chairman.email" label="Email" outlined dense class="col-6" />
          </div>
          <q-toggle v-model="hasTreasurer" label="Есть отдельный казначей" />
          <div v-if="hasTreasurer" class="row q-col-gutter-sm q-mt-xs">
            <q-input v-model="treasurer.last_name" label="Фамилия *" outlined dense class="col-12 col-sm-4" />
            <q-input v-model="treasurer.first_name" label="Имя *" outlined dense class="col-6 col-sm-4" />
            <q-input v-model="treasurer.patronymic" label="Отчество" outlined dense class="col-6 col-sm-4" />
            <q-input v-model="treasurer.phone" label="Телефон" outlined dense class="col-6" />
            <q-input v-model="treasurer.email" label="Email" outlined dense class="col-6" />
          </div>
          <div v-else class="text-caption text-grey-7">
            Если казначея нет — его работу делает председатель, ему доступно всё.
          </div>
          <q-banner v-if="formError" dense rounded class="bg-red-1 text-negative q-mt-sm">
            {{ formError }}
          </q-banner>
          <q-stepper-navigation>
            <q-btn color="green-8" icon="check" label="Создать садоводство" :loading="saving"
                   :disable="!canCreate" @click="create" />
            <q-btn flat label="Назад" class="q-ml-sm" @click="step = 1" />
          </q-stepper-navigation>
        </template>

        <template v-else>
          <q-banner dense rounded class="bg-green-1 q-mb-sm">
            <template #avatar><q-icon name="task_alt" color="positive" /></template>
            Садоводство «{{ createdOrg.name }}» создано. Передайте логины и временные пароли —
            при первом входе сайт попросит сменить пароль.
          </q-banner>
          <AccountsCard :accounts="accounts" />
          <q-stepper-navigation>
            <q-btn color="green-8" label="Дальше" @click="step = 3" />
          </q-stepper-navigation>
        </template>
      </q-step>

      <!-- 3–5. Загрузки (по желанию) -->
      <q-step v-for="imp in imports" :key="imp.step" :name="imp.step" :title="imp.title"
              :caption="imp.done ? 'загружено' : 'по желанию'" :icon="imp.icon" :done="imp.done"
              :header-nav="created">
        <div class="text-body2 q-mb-sm">{{ imp.hint }}</div>
        <div v-if="imp.result" class="text-body2 text-positive q-mb-sm">
          Загружено: {{ imp.result }}
        </div>
        <q-stepper-navigation>
          <q-btn outline color="green-8" icon="upload_file"
                 :label="imp.done ? 'Загрузить ещё файл' : 'Загрузить из Excel'"
                 @click="openImport(imp)" />
          <q-btn color="green-8" :label="imp.done ? 'Дальше' : 'Пропустить'" class="q-ml-sm"
                 @click="step = imp.step + 1" />
        </q-stepper-navigation>
      </q-step>

      <!-- 6. Готово -->
      <q-step :name="6" title="Готово" icon="flag" :header-nav="created">
        <div class="text-body1 q-mb-sm">Садоводство «{{ createdOrg?.name }}» настроено.</div>
        <ul class="q-mt-none text-body2">
          <li v-for="imp in imports" :key="imp.step">
            {{ imp.title }}: {{ imp.result || 'пропущено — можно загрузить позже' }}
          </li>
        </ul>
        <AccountsCard :accounts="accounts" class="q-mb-md" />
        <q-btn color="green-8" icon="arrow_forward" label="Перейти в садоводство" @click="finish" />
      </q-step>
    </q-stepper>

    <ExcelImportDialog
      v-if="activeImport"
      v-model="importOpen"
      :title="activeImport.title"
      :hint="activeImport.hint"
      :endpoint="activeImport.endpoint"
      :template-endpoint="activeImport.templateEndpoint"
      :template-name="activeImport.templateName"
      @done="onImported"
    />
  </q-page>
</template>

<script setup>
import { ref, reactive, computed, defineComponent, h } from 'vue'
import { useQuasar, copyToClipboard, QBtn, QMarkupTable } from 'quasar'
import api from 'src/api/client'
import { useAuthStore } from 'stores/auth'
import ExcelImportDialog from 'components/ExcelImportDialog.vue'

const $q = useQuasar()
const auth = useAuthStore()

const step = ref(1)
const saving = ref(false)
const created = ref(false)
const createdOrg = ref(null)
const accounts = ref([])
const errors = ref({})
const formError = ref('')

const org = reactive({
  name: '', full_name: '', inn: '', kpp: '', ogrn: '', legal_address: '',
  phone: '', email: '', bank_account: '', bank_bic: '', bank_corr_account: '', bank_name: '',
})
const emptyPerson = () => ({ last_name: '', first_name: '', patronymic: '', phone: '', email: '' })
const chairman = reactive(emptyPerson())
const treasurer = reactive(emptyPerson())
const hasTreasurer = ref(true)

const filled = (p) => p.last_name.trim() && p.first_name.trim()
const canCreate = computed(() => org.name.trim() && filled(chairman)
  && (!hasTreasurer.value || filled(treasurer)))

const imports = reactive([
  {
    step: 3, title: 'Реестр членов', icon: 'groups', done: false, result: '',
    hint: 'Колонки «№ участка» и «ФИО» обязательны; соток, телефоны, email, «Сособственник» — по желанию. '
      + 'Председатель и казначей уже заведены — их участки привяжутся к ним по ФИО.',
    endpoint: '/members/import/', templateEndpoint: '/members/import-template/',
    templateName: 'Шаблон — реестр членов.xlsx',
    summary: (s) => `членов ${s['Члены: новые'] ?? 0}, участков ${s['Участки: новые'] ?? 0}`,
  },
  {
    step: 4, title: 'Долги', icon: 'request_quote', done: false, result: '',
    hint: 'Начальные остатки: участок, сумма, за что (членский, целевой, свет, прочее) и за какой год. '
      + 'Сначала загрузите реестр — участки берутся из него.',
    endpoint: '/billing/charges/import/', templateEndpoint: '/billing/charges/import-template/',
    templateName: 'Шаблон — долги.xlsx',
    summary: (s) => `долгов ${s['Долги внесены'] ?? 0}${s['Сумма внесённых долгов, ₽'] ? ' на ' + s['Сумма внесённых долгов, ₽'] + ' ₽' : ''}`,
  },
  {
    step: 5, title: 'Счётчики и показания', icon: 'speed', done: false, result: '',
    hint: 'Участок, номер счётчика, дата и показание; главный счётчик — «да» в колонке «Главный». '
      + 'Долг за свет можно указать здесь же — для нового счётчика.',
    endpoint: '/electricity/meters/import/', templateEndpoint: '/electricity/meters/import-template/',
    templateName: 'Шаблон — счётчики и показания.xlsx',
    summary: (s) => `счётчиков ${s['Счётчики: новые'] ?? 0}, показаний ${s['Показания: добавлены'] ?? 0}`,
  },
])
const activeImport = ref(null)
const importOpen = ref(false)

function openImport(imp) {
  activeImport.value = imp
  importOpen.value = true
}

function onImported(data) {
  const imp = activeImport.value
  const stats = Object.fromEntries(data.stats || [])
  imp.done = true
  imp.result = imp.result ? `${imp.result}; ${imp.summary(stats)}` : imp.summary(stats)
}

function personBody(p) {
  return Object.fromEntries(Object.entries(p).map(([k, v]) => [k, String(v || '').trim()]))
}

async function create() {
  saving.value = true
  errors.value = {}
  formError.value = ''
  try {
    const { data } = await api.post('/organizations/setup/', {
      organization: Object.fromEntries(Object.entries(org).map(([k, v]) => [k, String(v || '').trim()])),
      chairman: personBody(chairman),
      treasurer: hasTreasurer.value ? personBody(treasurer) : null,
    })
    createdOrg.value = data.organization
    accounts.value = data.accounts
    created.value = true
    // Дальше загрузки идут уже в новое садоводство.
    auth.setOrg(data.organization.id, data.organization.name)
  } catch (e) {
    const d = e.response?.data || {}
    if (d.organization && typeof d.organization === 'object') {
      errors.value = Object.fromEntries(
        Object.entries(d.organization).map(([k, v]) => [k, [].concat(v).join(' ')]))
      step.value = 1
      $q.notify({ type: 'negative', message: 'Проверьте реквизиты товарищества' })
    } else {
      formError.value = Object.values(d).flat()
        .map((v) => (typeof v === 'object' ? Object.values(v).flat().join(' ') : v)).join(' ')
        || 'Не получилось создать садоводство'
    }
  } finally {
    saving.value = false
  }
}

function finish() {
  // Полная перезагрузка: шапка, меню и логотип подтянутся уже для нового СНТ.
  window.location.assign('/dashboard')
}

// Карточка с логинами и паролями — показывается дважды (после создания и
// в итоге), поэтому вынесена. Пароли живут только в памяти страницы.
const AccountsCard = defineComponent({
  props: { accounts: { type: Array, default: () => [] } },
  setup(props) {
    const copyAll = () => {
      const text = props.accounts.map((a) =>
        `${a.role_display}: ${a.full_name}\nЛогин: ${a.username}\nВременный пароль: ${a.password}`,
      ).join('\n\n') + '\n\nВход: ' + window.location.origin
      copyToClipboard(text)
        .then(() => $q.notify({ type: 'positive', message: 'Скопировано' }))
        .catch(() => $q.notify({ type: 'negative', message: 'Не скопировалось — выделите вручную' }))
    }
    return () => h('div', [
      h(QMarkupTable, { flat: true, bordered: true, dense: true, class: 'q-mb-sm' }, () => [
        h('thead', h('tr', [h('th', { class: 'text-left' }, 'Роль'), h('th', { class: 'text-left' }, 'ФИО'),
          h('th', { class: 'text-left' }, 'Логин'), h('th', { class: 'text-left' }, 'Временный пароль')])),
        h('tbody', props.accounts.map((a) => h('tr', { key: a.username }, [
          h('td', a.role_display), h('td', a.full_name),
          h('td', { class: 'text-mono' }, a.username), h('td', { class: 'text-mono' }, a.password),
        ]))),
      ]),
      h('div', { class: 'row items-center q-gutter-sm' }, [
        h(QBtn, { flat: true, dense: true, noCaps: true, color: 'primary', icon: 'content_copy',
          label: 'Скопировать логины и пароли', onClick: copyAll }),
        h('span', { class: 'text-caption text-orange-9' },
          'Пароли показываются только сейчас. Потеряли — «Сбросить пароль» в карточке члена.'),
      ]),
    ])
  },
})
</script>

<style scoped>
.wizard { max-width: 900px; }
.text-mono { font-family: monospace; }
</style>
