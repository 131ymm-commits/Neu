export const meta = { name: 'div02b-pilot', description: 'DIV-02 ред. 3: CHAIN, SOLO_LONG, SEG1, SC, EST — точная траектория Коллатца, все значения выписываются', phases: [{ title: 'Руки' }] }
const QS = [{"id": "P0-0", "n": "9006397253175", "order": ["SOLO_LONG", "EST", "SEG1", "SC", "CHAIN"]}, {"id": "P0-1", "n": "9933496241130", "order": ["SEG1", "SC", "EST", "SOLO_LONG", "CHAIN"]}, {"id": "P0-2", "n": "4226994684876", "order": ["EST", "SOLO_LONG", "SEG1", "CHAIN", "SC"]}, {"id": "P1-0", "n": "1300334783837459", "order": ["SC", "SOLO_LONG", "CHAIN", "SEG1", "EST"]}, {"id": "P1-1", "n": "8701924550589029", "order": ["EST", "CHAIN", "SC", "SOLO_LONG", "SEG1"]}, {"id": "P1-2", "n": "9798361980904253", "order": ["SEG1", "CHAIN", "SC", "EST", "SOLO_LONG"]}, {"id": "P2-0", "n": "2435790714575528910", "order": ["EST", "SOLO_LONG", "CHAIN", "SC", "SEG1"]}, {"id": "P2-1", "n": "9349691138564718146", "order": ["CHAIN", "EST", "SEG1", "SOLO_LONG", "SC"]}, {"id": "P2-2", "n": "8182569554902707936", "order": ["SC", "SOLO_LONG", "EST", "SEG1", "CHAIN"]}]
const NO = "Не используй никакие инструменты и не открывай файлы: считай сам, в уме, опираясь только на текст ниже."
const K = 13
const M = 3
const RULE = 'Правило Коллатца (классический шаг): если число чётное, дели на 2; если нечётное, умножай на 3 и прибавляй 1. Один шаг — одно применение правила.'
const VALS = { type: 'object', properties: { values: { type: 'array', items: { type: 'string' }, description: 'значения после каждого шага по порядку, десятичной записью; последнее — 1, если дошёл' }, note: { type: 'string' } }, required: ['values', 'note'] }
const EST = { type: 'object', properties: { steps: { type: 'integer' }, lo: { type: 'integer' }, hi: { type: 'integer' }, note: { type: 'string' } }, required: ['steps', 'lo', 'hi', 'note'] }
const call = (p, label, schema) => agent(p, { label, phase: 'Руки', schema }).catch(e => ({ error: String(e) }))
const full = n => `${NO}\n\n${RULE}\n\nПройди путь числа ${n} до 1 точно, шаг за шагом, и выпиши значение после каждого шага (не само ${n}, а следующие), до первой 1 включительно. Не подменяй счёт оценкой; проверяй каждое умножение.`
const seg = n => full(n) + ' Работай отрезками по 60 шагов: после каждого отрезка перепроверь последнее число отрезка, прежде чем продолжать.'
const ARMS = {
  SOLO_LONG: q => call(full(q.n), `solo_long:${q.id}`, VALS),
  SEG1: q => call(seg(q.n), `seg1:${q.id}`, VALS),
  EST: q => call(`${NO}\n\n${RULE}\n\nСколько шагов нужно числу ${q.n}, чтобы впервые дойти до 1? Дай оценку steps и 80 % интервал lo, hi; note — метод одной фразой.`, `est:${q.id}`, EST),
  SC: q => parallel(Array.from({ length: M }, (_, k) => () => call(full(q.n), `sc${k + 1}:${q.id}`, VALS))),
  CHAIN: async q => { let v = q.n; const links = []
    for (let k = 0; k < K; k++) {
      const r = await call(`${NO}\n\n${RULE}\n\nТы — звено ${k + 1} в эстафете голов, которые вместе точно проходят путь числа. Начни с числа ${v}. Сделай ровно 60 шагов (или меньше, если раньше дойдёшь до 1) и выпиши значение после каждого шага по порядку. Проверяй каждое умножение.`, `chain:${q.id}:${k + 1}`, VALS)
      links.push(r); const vs = (r && r.values) || []; if (!vs.length || vs.includes('1')) break
      v = String(vs[vs.length - 1]).trim()
    } return links },
}
const out = {}
await parallel(QS.map(q => async () => { out[q.id] = {}
  for (const arm of q.order) out[q.id][arm] = await ARMS[arm](q) }))
return out
