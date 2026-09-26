export const meta = { name: 'div02-run', description: 'DIV-02: одна голова, цепочка голов по 60 шагов и самосогласование с равным бюджетом — точный счёт шагов Коллатца', phases: [{ title: 'Одна голова' }, { title: 'Цепочка' }, { title: 'Самосогласование' }] }
const QS = null
const NO = null
const LINK_STEPS = null, MAX_LINKS = null, SC_MIN = null
const RULE = 'Правило Коллатца: если число чётное, дели на 2; если нечётное, умножай на 3 и прибавляй 1. Один шаг — одно применение правила.'
const SOLO = { type: 'object', properties: { steps: { type: 'integer' }, lo: { type: 'integer' }, hi: { type: 'integer' }, done: { type: 'boolean' }, note: { type: 'string' } }, required: ['steps', 'lo', 'hi', 'done', 'note'] }
const LINK = { type: 'object', properties: { value: { type: 'string', description: 'текущее число после твоих шагов, десятичной записью' }, steps_done: { type: 'integer' }, reached_one: { type: 'boolean' } }, required: ['value', 'steps_done', 'reached_one'] }
const soloPrompt = n => `${NO}\n\n${RULE}\n\nСколько шагов нужно числу ${n}, чтобы впервые дойти до 1? Считай точно, шаг за шагом, не подменяй счёт средней оценкой. Верни steps — число шагов, lo и hi — 80 % интервал, done — удалось ли досчитать до 1 точно, note — как считал.`
const soloCall = (q, k, phase) => agent(soloPrompt(q.n), { label: `${phase === 'Одна голова' ? 'solo' : 'sc' + k}:${q.id}`, phase, schema: SOLO }).catch(e => null)
const solo = {}, chain = {}, sc = {}
await parallel(QS.map(q => async () => { solo[q.id] = await soloCall(q, 0, 'Одна голова') }))
await parallel(QS.map(q => async () => {
  let v = String(q.n), total = 0, links = [], done = false
  for (let k = 0; k < MAX_LINKS; k++) {
    const r = await agent(`${NO}\n\n${RULE}\n\nТы — звено ${k + 1} в эстафете голов, которые вместе точно считают траекторию. Начни с числа ${v}. Сделай точно ${LINK_STEPS} шагов (или меньше, если раньше дойдёшь до 1), проверяя каждое умножение. Верни число после твоих шагов, сколько шагов сделал и дошёл ли до 1.`, { label: `chain:${q.id}:${k + 1}`, phase: 'Цепочка', schema: LINK }).catch(e => null)
    links.push(r); if (!r) break
    total += r.steps_done; v = r.value; if (r.reached_one || v === '1') { done = true; break }
  }
  chain[q.id] = { steps: total, links, done, last: v }
  const m = Math.max(SC_MIN, links.length)
  sc[q.id] = await parallel(Array.from({ length: m }, (_, k) => () => soloCall(q, k + 1, 'Самосогласование')))
}))
return { solo, chain, sc }
