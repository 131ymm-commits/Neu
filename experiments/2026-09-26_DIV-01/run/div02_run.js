export const meta = { name: 'div02-run', description: 'DIV-02: одна голова, цепочка голов по 60 шагов и самосогласование с равным бюджетом — точный счёт шагов Коллатца', phases: [{ title: 'Одна голова' }, { title: 'Цепочка' }, { title: 'Самосогласование' }] }
const QS = [{"id": "CZ0-0", "n": "4191281270084"}, {"id": "CZ0-1", "n": "9639207694622"}, {"id": "CZ0-2", "n": "9417430687659"}, {"id": "CZ0-3", "n": "5753632188350"}, {"id": "CZ0-4", "n": "7625355946829"}, {"id": "CZ0-5", "n": "6309907510002"}, {"id": "CZ0-6", "n": "4506858279209"}, {"id": "CZ0-7", "n": "9710964484758"}, {"id": "CZ1-0", "n": "1777054913321819"}, {"id": "CZ1-1", "n": "3219076579880282"}, {"id": "CZ1-2", "n": "1419575748366186"}, {"id": "CZ1-3", "n": "1938903097542182"}, {"id": "CZ1-4", "n": "8079838960102566"}, {"id": "CZ1-5", "n": "7751551100014215"}, {"id": "CZ1-6", "n": "7775109389241889"}, {"id": "CZ1-7", "n": "7971506651735016"}, {"id": "CZ2-0", "n": "4192131730874000124"}, {"id": "CZ2-1", "n": "9629193551318539659"}, {"id": "CZ2-2", "n": "7480698032414687395"}, {"id": "CZ2-3", "n": "5164965246045953256"}, {"id": "CZ2-4", "n": "2699462414687575312"}, {"id": "CZ2-5", "n": "4227101265806041070"}, {"id": "CZ2-6", "n": "2984859673114535955"}, {"id": "CZ2-7", "n": "3201048192165107221"}]
const NO = "Не используй никакие инструменты и не открывай файлы: считай сам, в уме, опираясь только на текст ниже."
const LINK_STEPS = 60, MAX_LINKS = 12, SC_MIN = 3
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
