// Деньги на всём сайте пишутся одинаково: «1 234 ₽», «827,45 ₽».
//
// Копейки — только когда они есть. Раньше страницы делали кто во что
// горазд: «Начисления» и главная округляли до рубля (долг 827,45
// показывался как 827 и не сходился с выпиской), выписка писала
// «1 000,00», смета — «1 000,00 ₽». Разделитель разрядов — неразрывный
// пробел (так его ставит toLocaleString), поэтому сумма не рвётся
// на две строки.

function amount(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

// Число без знака рубля — для мест, где ₽ стоит в подписи рядом.
export function formatMoney(v) {
  const n = amount(v)
  const kopecks = Math.round(Math.abs(n) * 100) % 100 !== 0
  return n.toLocaleString('ru-RU', {
    minimumFractionDigits: kopecks ? 2 : 0,
    maximumFractionDigits: 2,
  })
}

// Сумма со знаком рубля; пустое значение — прочерк.
export function rub(v) {
  if (v === null || v === undefined || v === '') return '—'
  return `${formatMoney(v)} ₽`
}
