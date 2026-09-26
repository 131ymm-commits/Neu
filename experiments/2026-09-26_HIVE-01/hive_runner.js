export const meta = {
  name: 'hive-runner',
  description: 'HIVE-01: исполняет готовые промпты (головы улья отвечают пачкой оценок без инструментов; мутатор переписывает законы) с проверкой формата',
  phases: [{ title: 'Вызовы' }],
}
// args: {part, calls: [{label, alias, kind: batch|laws, ids?, prompt}]}
const now = () => { try { return new Date().toISOString() } catch (e) { return 'не контролируется' } }
const obj = (props, req) => ({ type: 'object', properties: props, required: req })
const SCHEMA = {
  batch: obj({ items: { type: 'array', items: obj({ id: { type: 'string' }, estimate: { type: 'number' }, lo: { type: 'number' }, hi: { type: 'number' },
    note: { type: 'string', description: 'метод, одна фраза' } }, ['id', 'estimate', 'lo', 'hi', 'note']) } }, ['items']),
  laws: obj({ laws: { type: 'array', items: { type: 'string' } }, rationale: { type: 'string' } }, ['laws', 'rationale']),
}
const check = c => r => {
  if (c.kind === 'laws') return (Array.isArray(r.laws) && r.laws.length >= 1 && r.laws.length <= 8) ? null : 'формат законов'
  const got = new Map((r.items || []).map(x => [x.id, x]))
  const bad = c.ids.filter(i => { const x = got.get(i); return !x || ![x.estimate, x.lo, x.hi].every(v => typeof v === 'number' && isFinite(v)) || !(x.lo <= x.estimate && x.estimate <= x.hi) })
  return bad.length ? `плохих ${bad.length}` : null
}
const records = []
async function run(c) {
  for (let a = 0; a < 3; a++) {
    let res = null, err = null
    try { res = await agent(c.prompt, { label: a ? `${c.alias}#retry${a}` : c.alias, phase: 'Вызовы', schema: SCHEMA[c.kind] }) } catch (e) { err = String(e) }
    const problem = err || (res == null ? 'пустой ответ' : check(c)(res))
    records.push({ part: args.part, label: c.label, alias: c.alias, attempt: a, retry: a > 0, t: now(), how: 'workflow agent() со схемой', prompt: c.prompt, response: res, problem })
    if (!problem) return
  }
}
await parallel(args.calls.map(c => () => run(c)))
return { part: args.part, records }
