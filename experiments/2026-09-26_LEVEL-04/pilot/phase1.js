export const meta = { name: 'level04-phase1', description: 'LEVEL-04: организации голов (длина звена s, проверка v, дублирование r) проходят цепочки x → x²+c mod p; фаза 1 или 2', phases: [{ title: 'Организации' }] }
const JOBS = [{"id": "s200:P1C0", "geno": {"s": 200, "v": 0, "r": 1}, "chain": {"id": "P1C0", "x": 807672519, "c": 520, "p": 1000000007, "L": 200}}, {"id": "s200:P1C1", "geno": {"s": 200, "v": 0, "r": 1}, "chain": {"id": "P1C1", "x": 210973257, "c": 375, "p": 1000000007, "L": 200}}, {"id": "s40:P1C0", "geno": {"s": 40, "v": 0, "r": 1}, "chain": {"id": "P1C0", "x": 807672519, "c": 520, "p": 1000000007, "L": 200}}, {"id": "s40:P1C1", "geno": {"s": 40, "v": 0, "r": 1}, "chain": {"id": "P1C1", "x": 210973257, "c": 375, "p": 1000000007, "L": 200}}, {"id": "s10:P1C0", "geno": {"s": 10, "v": 0, "r": 1}, "chain": {"id": "P1C0", "x": 807672519, "c": 520, "p": 1000000007, "L": 200}}, {"id": "s10:P1C1", "geno": {"s": 10, "v": 0, "r": 1}, "chain": {"id": "P1C1", "x": 210973257, "c": 375, "p": 1000000007, "L": 200}}]   // [{geno:{s,v,r}, chain:{id,x,c,p,L}}]
const NO = 'Не используй никакие инструменты, не исполняй код и не пользуйся калькулятором: считай сам, в уме, опираясь только на текст ниже.'
const V = { type: 'object', properties: { check: { type: 'string', description: 'если просили пересчитать шаг: твой результат этого шага, иначе пусто' }, values: { type: 'array', items: { type: 'string' } } }, required: ['check', 'values'] }
const last = r => (r && Array.isArray(r.values) && r.values.length) ? String(r.values[r.values.length - 1]).trim() : null
const records = []
async function link(ch, from, m, tag, prevStep) {
  const chk = prevStep ? `Сначала проверь предыдущее звено: пересчитай один шаг из ${prevStep[0]} и запиши результат в check (у предыдущего звена вышло ${prevStep[1]}). ` : ''
  const p = `${NO}\n\nИтерация: x_{k+1} = (x_k² + ${ch.c}) mod ${ch.p}. ${chk}Начни с ${from}. Сделай точно ${m} шагов и выпиши значения после каждого шага по порядку, десятичной записью. Проверяй каждое умножение и остаток.`
  const r = await agent(p, { label: tag, phase: 'Организации', schema: V }).catch(e => ({ error: String(e) }))
  records.push({ tag, from, m, check: r && r.check, n: r && r.values && r.values.length }); return r
}
async function runOrg(g, ch, jid) {
  let x = String(ch.x), calls = 0, prev = null, k = 0
  const n = Math.ceil(ch.L / g.s)
  for (let i = 0; i < n; i++) {
    const m = Math.min(g.s, ch.L - i * g.s), tag = `${jid}:L${i + 1}`
    let res, out
    if (g.r === 1) { res = await link(ch, x, m, tag, g.v ? prev : null); calls++; out = last(res) }
    else {
      const [a, b] = await Promise.all([link(ch, x, m, tag + 'a', g.v ? prev : null), link(ch, x, m, tag + 'b', g.v ? prev : null)]); calls += 2
      res = a; out = last(a)
      if (last(a) !== last(b)) { const c3 = await link(ch, x, m, tag + 'c', null); calls++; const vs = [last(a), last(b), last(c3)]; out = vs.find(v => vs.filter(w => w === v).length >= 2) || last(c3) }
    }
    if (g.v && prev && res && String(res.check || '').trim() && String(res.check).trim() !== prev[1]) {  // проверка: предыдущее звено пересчитывается один раз
      const redo = await link(ch, prev[2], prev[3], tag + ':redo', null); calls++
      const fixed = last(redo)
      if (fixed && fixed !== x) { x = fixed; i--; prev = null; continue }  // продолжаем с исправленного значения, текущее звено заново
    }
    const vals = (res && res.values) || []
    prev = [vals.length > 1 ? String(vals[vals.length - 2]).trim() : x, out, x, m]
    x = out || x
  }
  return { final: x, calls }
}
const out = {}
await parallel(JOBS.map((j, idx) => async () => { out[j.id] = await runOrg(j.geno, j.chain, j.id) }))
return { out, records }
