export const meta = { name: 'div02-pilot', description: 'DIV-02 пилот: точный счёт траектории Коллатца — одна голова против цепочки голов с передачей эстафеты', phases: [{ title: 'Одна голова' }, { title: 'Цепочка' }] }
const QS = [{"id": "CZ-91000", "n": 224758724117}, {"id": "CZ-91001", "n": 788984232435}, {"id": "CZ-91002", "n": 232461125563}, {"id": "CZ-91003", "n": 573618286127}]
const NO = "Не используй никакие инструменты и не открывай файлы: считай сам, в уме, опираясь только на текст ниже."
const SOLO = { type: 'object', properties: { steps: { type: 'integer' }, lo: { type: 'integer' }, hi: { type: 'integer' }, done: { type: 'boolean' }, note: { type: 'string' } }, required: ['steps', 'lo', 'hi', 'done', 'note'] }
const LINK = { type: 'object', properties: { value: { type: 'string', description: 'текущее число после твоих шагов, десятичной записью' }, steps_done: { type: 'integer', description: 'сколько шагов ты сделал' }, reached_one: { type: 'boolean' } }, required: ['value', 'steps_done', 'reached_one'] }
const RULE = 'Правило Коллатца: если число чётное, дели на 2; если нечётное, умножай на 3 и прибавляй 1. Один шаг — одно применение правила.'
const records = []
const solo = await parallel(QS.map(q => () => agent(`${NO}\n\n${RULE}\n\nСколько шагов нужно числу ${q.n}, чтобы впервые дойти до 1? Считай точно, шаг за шагом, не подменяй счёт средней оценкой. Верни steps — число шагов, lo и hi — 80 % интервал, done — удалось ли досчитать до 1 точно, note — как считал.`, { label: `solo:${q.id}`, phase: 'Одна голова', schema: SOLO }).catch(e => ({ error: String(e) }))))
const chain = await parallel(QS.map(q => async () => {
  let v = String(q.n), total = 0, links = []
  for (let k = 0; k < 8; k++) {
    const r = await agent(`${NO}\n\n${RULE}\n\nТы — звено ${k + 1} в эстафете голов, которые вместе точно считают траекторию. Начни с числа ${v}. Сделай точно 60 шагов (или меньше, если раньше дойдёшь до 1), проверяя каждое умножение. Верни число после твоих шагов, сколько шагов сделал и дошёл ли до 1.`, { label: `chain:${q.id}:${k + 1}`, phase: 'Цепочка', schema: LINK }).catch(e => ({ error: String(e) }))
    links.push(r); if (!r || r.error) break
    total += r.steps_done; v = r.value; if (r.reached_one || v === '1') return { steps: total, links, done: true }
  }
  return { steps: total, links, done: false }
}))
return { solo, chain }
