export const meta = { name: 'level05-matryoshka', description: 'LEVEL-05 матрёшка: ансамбль голов как агент следующего уровня (1 → 5 → 10 → 20 голов), один интерфейс {ответ, уверенность, довод}', phases: [{ title: 'Решатели' }, { title: 'Уровень 2' }, { title: 'Уровень 3' }, { title: 'Уровень 4' }] }
const TASKS = null   // [{id, text}]
const NO = 'Не используй никакие инструменты, не исполняй код и не открывай файлы: думай сам, опираясь только на текст ниже.'
const OUT = { type: 'object', properties: { answer: { type: 'string', description: 'итоговое число (только цифры)' }, confidence: { type: 'number', description: 'вероятность от 0 до 1, что ответ отличается от правды не более чем на 1 %' }, reason: { type: 'string', description: 'довод в 1–3 фразах' } }, required: ['answer', 'confidence', 'reason'] }
const METHODS = [
  'Реши напрямую, аккуратно, с проверкой каждого шага.',
  'Реши другим способом, чем решали бы обычно: иная формула, иная декомпозиция, иной порядок счёта.',
  'Сначала оцени границы и порядок величины ответа, затем уточни до числа.',
  'Сначала перечисли, в чём чаще всего ошибаются в таких задачах, затем реши, избегая этих ошибок.',
]
const CRIT = 'Ответ считается верным, если отличается от правды не более чем на 1 %.'
const call = (p, o) => agent(p, o).catch(() => agent(p, o).catch(() => null))
const show = (xs) => xs.map((x, i) => `Участник ${i + 1}: ответ ${x ? x.answer : '— (нет ответа)'}; уверенность ${x ? x.confidence : '—'}; довод: ${x ? x.reason : '—'}`).join('\n')
async function solver(t, k) {
  return call(`${NO}\n\nЗадача: ${t.text}\n${CRIT}\n\nМетод: ${METHODS[k % 4]}\n\nВерни answer (число), confidence и reason.`, { label: `S${k}:${t.id}`, phase: 'Решатели', schema: OUT })
}
async function integrate(t, parts, level, tag) {
  return call(`${NO}\n\nТы — интегратор ансамбля. Задача: ${t.text}\n${CRIT}\n\nНиже — выходы участников ансамбля (каждый — отдельный агент; правды у тебя нет):\n${show(parts)}\n\nСведи их в один ответ ансамбля: взвесь согласие, доводы и уверенности, проверь спорное сам. Верни answer, confidence (честную: если участники расходятся и ты не можешь разрешить спор, уверенность должна быть низкой) и reason.`, { label: `I${level}${tag}:${t.id}`, phase: `Уровень ${level}`, schema: OUT })
}
const out = {}
await parallel(TASKS.map(t => async () => {
  const S = await Promise.all([...Array(16).keys()].map(k => solver(t, k)))
  const L2 = await Promise.all([0, 1, 2, 3].map(u => integrate(t, S.slice(4 * u, 4 * u + 4), 2, String.fromCharCode(97 + u))))
  const L3 = await Promise.all([0, 1].map(u => integrate(t, L2.slice(2 * u, 2 * u + 2), 3, String.fromCharCode(97 + u))))
  const L4 = await integrate(t, L3, 4, 'a')
  out[t.id] = { S, L2, L3, L4 }
}))
return { out }
