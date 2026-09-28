export const meta = { name: 'level05-calib', description: 'LEVEL-05 калибровка горизонта: одна голова перемножает M матриц 2×2 по модулю p (M = 5, 10, 20, 40); повтор M = 10 для корреляции ошибок', phases: [{ title: 'Калибровка' }] }
const TASKS = null
const NO = 'Не используй никакие инструменты, не исполняй код и не открывай файлы: считай сам, в уме, опираясь только на текст ниже.'
const OUT = { type: 'object', properties: { a: { type: 'string' }, b: { type: 'string' }, c: { type: 'string' }, d: { type: 'string' }, confidence: { type: 'number', description: 'вероятность от 0 до 1, что все четыре числа точны' } }, required: ['a', 'b', 'c', 'd', 'confidence'] }
const fmt = m => `[[${m[0][0]}, ${m[0][1]}], [${m[1][0]}, ${m[1][1]}]]`
const call = (p, o) => agent(p, o).catch(() => agent(p, o).catch(() => null))
const out = {}
await parallel(TASKS.flatMap(t => (t.M === 10 ? [0, 1] : [0]).map(rep => async () => {
  const p = `${NO}\n\nПеремножь по порядку ${t.M} матриц 2×2 по модулю ${t.p} (после каждого умножения бери остаток по модулю ${t.p}):\n${t.matrices.map((m, i) => `M${i + 1} = ${fmt(m)}`).join('\n')}\n\nНайди M1·M2·…·M${t.M} mod ${t.p} = [[a, b], [c, d]]. Верни a, b, c, d и confidence.`
  out[`${t.id}#${rep}`] = await call(p, { label: `${t.id}#${rep}`, phase: 'Калибровка', schema: OUT })
})))
return { out }
