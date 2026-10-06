<template>
  <q-dialog :model-value="modelValue" persistent @update:model-value="(v) => emit('update:modelValue', v)">
    <q-card style="width:560px;max-width:96vw">
      <q-card-section class="row items-center q-pb-none">
        <div class="text-h6">{{ title }}</div>
        <q-space />
        <q-btn flat round dense icon="close" @click="close" />
      </q-card-section>

      <q-card-section>
        <div class="text-body2 q-mb-sm">{{ hint }}</div>
        <q-btn flat dense no-caps color="primary" icon="download" label="Скачать шаблон"
               :loading="templateLoading" @click="downloadTemplate" />
      </q-card-section>

      <q-card-section class="q-pt-none">
        <q-file v-model="file" label="Файл Excel (.xlsx)" outlined dense
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                @update:model-value="report = null">
          <template #prepend><q-icon name="table_view" /></template>
        </q-file>
      </q-card-section>

      <q-card-section v-if="report" class="q-pt-none">
        <q-banner dense rounded :class="report.dry_run ? 'bg-blue-1' : 'bg-green-1'" class="q-mb-sm">
          <template #avatar>
            <q-icon :name="report.dry_run ? 'fact_check' : 'task_alt'"
                    :color="report.dry_run ? 'primary' : 'positive'" />
          </template>
          {{ report.dry_run
            ? `Проверка: строк с данными — ${report.rows}. Пока ничего не записано.`
            : `Загружено: строк с данными — ${report.rows}.` }}
        </q-banner>
        <q-markup-table flat dense bordered class="q-mb-sm">
          <tbody>
            <tr v-for="[label, value] in report.stats" :key="label">
              <td>{{ label }}</td>
              <td class="text-right text-weight-medium">{{ value }}</td>
            </tr>
          </tbody>
        </q-markup-table>
        <div v-if="report.issues.length" class="import-issues">
          <div class="text-subtitle2 text-orange-9 q-mb-xs">
            Требуют внимания ({{ report.issues.length }}):
          </div>
          <ul class="q-my-none q-pl-md text-body2">
            <li v-for="(line, i) in report.issues" :key="i">{{ line }}</li>
          </ul>
        </div>
        <div v-else class="text-positive text-body2">Замечаний нет.</div>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat label="Закрыть" @click="close" />
        <q-btn outline color="primary" icon="fact_check" label="Проверить"
               :disable="!file" :loading="busy === 'check'" @click="run(true)" />
        <q-btn unelevated color="green-8" icon="upload" label="Загрузить"
               :disable="!file || !checked" :loading="busy === 'load'" @click="run(false)">
          <q-tooltip v-if="file && !checked">Сначала «Проверить»</q-tooltip>
        </q-btn>
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useQuasar } from 'quasar'
import api from 'src/api/client'

const props = defineProps({
  modelValue: Boolean,
  title: { type: String, required: true },
  hint: { type: String, default: '' },
  endpoint: { type: String, required: true },
  templateEndpoint: { type: String, required: true },
  templateName: { type: String, default: 'Шаблон.xlsx' },
})
const emit = defineEmits(['update:modelValue', 'done'])

const $q = useQuasar()
const file = ref(null)
const report = ref(null)
const busy = ref('')
const templateLoading = ref(false)
// «Загрузить» — только после проверки этого же файла: отчёт проверки
// показывает, что именно запишется, и пропустить его легко по привычке.
const checked = computed(() => !!report.value && report.value.dry_run)

function errorText(e) {
  const d = e.response?.data
  if (d && typeof d === 'object') return Object.values(d).flat().join(' ')
  return 'Не получилось'
}

async function run(dryRun) {
  busy.value = dryRun ? 'check' : 'load'
  try {
    const form = new FormData()
    form.append('file', file.value)
    form.append('dry_run', dryRun ? 'true' : 'false')
    const { data } = await api.post(props.endpoint, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    report.value = data
    if (!dryRun) {
      $q.notify({ type: 'positive', message: 'Загружено' })
      emit('done', data)
    }
  } catch (e) {
    report.value = null
    $q.notify({ type: 'negative', message: errorText(e), multiLine: true, timeout: 8000 })
  } finally {
    busy.value = ''
  }
}

async function downloadTemplate() {
  templateLoading.value = true
  try {
    const { data } = await api.get(props.templateEndpoint, { responseType: 'blob' })
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = props.templateName
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch {
    $q.notify({ type: 'negative', message: 'Шаблон не скачался' })
  } finally {
    templateLoading.value = false
  }
}

function close() {
  file.value = null
  report.value = null
  emit('update:modelValue', false)
}
</script>

<style scoped>
.import-issues {
  max-height: 240px;
  overflow-y: auto;
}
</style>
