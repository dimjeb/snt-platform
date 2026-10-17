<template>
  <div class="help-page">
    <div class="help-bar">
      <div class="help-bar-inner">
        <q-btn flat dense icon="arrow_back" :label="backLabel" @click="goBack" />
        <div v-if="title" class="q-ml-md text-subtitle1 ellipsis">{{ title }}</div>
        <q-space />
        <q-btn
          flat dense icon="print" label="Распечатать"
          class="gt-xs" @click="print"
        />
      </div>
    </div>

    <div v-if="loading" class="row justify-center q-pa-xl"><q-spinner color="primary" size="32px" /></div>
    <div v-else-if="loadError" class="help-body text-negative">{{ loadError }}</div>
    <article v-else class="help-body" v-html="html" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import { useAuthStore } from 'stores/auth'
import api from 'src/api/client'
import { filterHelp, visibleSections } from 'src/utils/helpByRole'

// Инструкция читается из того же файла, что лежит в docs/ и правится
// вместе с кодом. Копии не делаем: две инструкции разъезжаются в первый
// же месяц, и человек читает ту, которая врёт.
import source from '../../../docs/Инструкция.md?raw'

// remote — адрес API, откуда взять текст вместо вшитой инструкции:
// так открывается руководство администратора, которое в сборку не
// попадает и отдаётся сервером только администратору платформы.
const props = defineProps({
  remote: { type: String, default: '' },
  title: { type: String, default: '' },
})
const remoteSource = ref('')
const loading = ref(!!props.remote)
const loadError = ref('')

onMounted(async () => {
  if (!props.remote) return
  try {
    const { data } = await api.get(props.remote)
    remoteSource.value = data.markdown || ''
  } catch (e) {
    loadError.value = e.response?.status === 403
      ? 'Эта страница доступна только администратору платформы.'
      : 'Не удалось загрузить руководство.'
  } finally {
    loading.value = false
  }
})

const router = useRouter()
const auth = useAuthStore()

const backLabel = computed(() => (auth.isAuthenticated ? 'На главную' : 'Ко входу'))

function goBack() {
  router.push(auth.isAuthenticated ? '/dashboard' : '/login')
}

function print() {
  window.print()
}

// Свои идентификаторы у заголовков: оглавление в начале инструкции
// ссылается на «#я-садовод» и подобные, а marked сам их не проставляет.
function slug(text) {
  return String(text)
    .toLowerCase()
    .replace(/<[^>]+>/g, '')
    .replace(/[^\p{L}\p{N}\s-]/gu, '')
    .trim()
    .replace(/\s+/g, '-')
}

const renderer = new marked.Renderer()
renderer.heading = function ({ tokens, depth }) {
  const text = this.parser.parseInline(tokens)
  return `<h${depth} id="${slug(this.parser.parseInline(tokens, this.parser.textRenderer))}">${text}</h${depth}>\n`
}

// После входа — только разделы для роли человека; до входа роль
// неизвестна, показываем всё, кроме раздела администратора платформы.
const ownSource = computed(() => {
  const visible = visibleSections({
    authenticated: auth.isAuthenticated,
    role: auth.user?.role,
    hasOwnCabinet: auth.hasOwnCabinet,
  })
  let text = filterHelp(source, visible)
  if (auth.isAuthenticated) {
    text = text.replace('Сначала найдите свой раздел:', 'Здесь — разделы для вас:')
  }
  return text
})

const html = computed(() =>
  marked.parse(props.remote ? remoteSource.value : ownSource.value,
    { renderer, gfm: true, breaks: false }),
)
</script>

<style scoped>
.help-page {
  min-height: 100vh;
  background: #fff;
}

.help-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: #2d6a4f;
  color: #fff;
}
.help-bar-inner {
  display: flex;
  align-items: center;
  max-width: 820px;
  margin: 0 auto;
  padding: 4px 12px;
}

.help-body {
  max-width: 820px;
  margin: 0 auto;
  padding: 24px 16px 64px;
  font-size: 16px;
  line-height: 1.65;
  color: #23301f;
}

.help-body :deep(h1) {
  font-size: 28px;
  line-height: 1.25;
  margin: 8px 0 20px;
  color: #1b4332;
}
.help-body :deep(h2) {
  font-size: 23px;
  margin: 40px 0 12px;
  padding-top: 20px;
  border-top: 1px solid #dfe7df;
  color: #1b4332;
}
.help-body :deep(h3) {
  font-size: 19px;
  margin: 28px 0 8px;
  color: #2d6a4f;
}

.help-body :deep(p) { margin: 0 0 12px; }
.help-body :deep(ol),
.help-body :deep(ul) { margin: 0 0 14px; padding-left: 26px; }
.help-body :deep(li) { margin-bottom: 6px; }

.help-body :deep(a) { color: #2d6a4f; }

/* Предупреждения и пояснения — самое ценное в инструкции, их должно
   быть видно при беглом просмотре. */
.help-body :deep(blockquote) {
  margin: 14px 0;
  padding: 10px 14px;
  border-left: 4px solid #f0a202;
  background: #fff8e7;
  border-radius: 0 6px 6px 0;
}
.help-body :deep(blockquote p:last-child) { margin-bottom: 0; }

.help-body :deep(code) {
  background: #eef3ee;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.9em;
  word-break: break-word;
}
.help-body :deep(pre) {
  background: #22311f;
  color: #e8f0e6;
  padding: 12px 14px;
  border-radius: 8px;
  overflow-x: auto;
}
.help-body :deep(pre code) {
  background: none;
  color: inherit;
  padding: 0;
}

.help-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 14px 0;
  font-size: 15px;
}
.help-body :deep(th),
.help-body :deep(td) {
  border: 1px solid #dfe7df;
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}
.help-body :deep(th) { background: #f2f7f2; }

.help-body :deep(hr) {
  border: 0;
  border-top: 1px solid #dfe7df;
  margin: 32px 0;
}

@media print {
  .help-bar { display: none; }
  .help-body { max-width: none; padding: 0; }
}
</style>
