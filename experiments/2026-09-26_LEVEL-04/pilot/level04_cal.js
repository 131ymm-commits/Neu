export const meta = { name: 'level04-cal', description: 'LEVEL-04 калибровка: ошибка на шаг у одной головы в итерации x → x² + c (mod p), p ≈ 10⁹, 30 шагов, по 3 головы на цепочку', phases: [{ title: 'Калибровка' }] }
const QS = [{"id": "M0", "x": "894196155", "c": 506, "p": "1000000007"}, {"id": "M1", "x": "370810213", "c": 191, "p": "1000000007"}, {"id": "M2", "x": "722138664", "c": 727, "p": "1000000007"}, {"id": "M3", "x": "781203969", "c": 697, "p": "1000000007"}]
const NO = "Не используй никакие инструменты и не открывай файлы: считай сам, в уме, опираясь только на текст ниже."
const V = { type: 'object', properties: { values: { type: 'array', items: { type: 'string' } }, note: { type: 'string' } }, required: ['values', 'note'] }
const out = {}
await parallel(QS.map(q => async () => { out[q.id] = await parallel([1, 2, 3].map(k => () => agent(`${NO}\n\nИтерация: x_{k+1} = (x_k² + ${q.c}) mod ${q.p}. Начальное x_0 = ${q.x}. Посчитай точно 30 шагов и выпиши x_1 … x_30 по порядку, десятичной записью. Проверяй каждое умножение и остаток.`, { label: `cal:${q.id}:${k}`, phase: 'Калибровка', schema: V }).catch(() => null))) }))
return out
