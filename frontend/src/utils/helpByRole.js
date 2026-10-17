// Инструкция по ролям: после входа человек видит только свои разделы.
//
// Текст один (docs/Инструкция.md), режется по заголовкам второго уровня.
// Разделы «Первый вход» и «Если что-то пошло не так» нужны всем;
// ролевые — по таблице ниже. Садоводу незачем листать полсотни шагов
// казначея, а пункты, которых у человека нет в меню, только путают.

const ROLE_SECTIONS = {
  'Я садовод': 'gardener',
  'Я казначей': 'treasurer',
  'Я председатель': 'chairman',
  'Я администратор платформы': 'platform',
}

// Какие ролевые разделы показывать. Председателю доступно всё, что
// казначею; свой участок (кабинет садовода) бывает и у правления.
export function visibleSections({ authenticated, role, hasOwnCabinet }) {
  if (!authenticated) return new Set(['gardener', 'treasurer', 'chairman'])
  if (role === 'superadmin') return new Set(Object.values(ROLE_SECTIONS))
  const set = new Set()
  if (role === 'member' || hasOwnCabinet) set.add('gardener')
  if (role === 'treasurer' || role === 'chairman') set.add('treasurer')
  if (role === 'chairman') set.add('chairman')
  return set
}

export function filterHelp(markdown, visible) {
  // Делим на «шапку» (до первого ##) и разделы.
  const parts = markdown.split(/^(?=## )/m)
  const head = parts.shift()
  const kept = parts.filter((part) => {
    const title = part.slice(3, part.indexOf('\n')).trim()
    const key = ROLE_SECTIONS[title]
    return !key || visible.has(key)
  })
  // В оглавлении шапки — только ссылки на оставшиеся разделы.
  const hiddenAnchors = Object.entries(ROLE_SECTIONS)
    .filter(([, key]) => !visible.has(key))
    .map(([title]) => '#' + title.toLowerCase().replace(/\s+/g, '-'))
  const headFiltered = head
    .split('\n')
    .filter((line) => !hiddenAnchors.some((a) => line.includes(`](${a})`)))
    .join('\n')
  return headFiltered + kept.join('')
}
