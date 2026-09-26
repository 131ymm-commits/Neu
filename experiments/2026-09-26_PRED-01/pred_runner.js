export const meta = {
  name: 'pred-runner',
  description: 'PRED-01: исполняет готовые промпты (головы дают оценку и 80 % интервал без инструментов) с проверкой формата и техническими повторами',
  phases: [{ title: 'Вызовы' }],
}
// args: {part, calls: [{label, alias, prompt}]}
const now = () => { try { return new Date().toISOString() } catch (e) { return 'не контролируется' } }
const SCHEMA = { type: 'object', properties: { estimate: { type: 'number' }, lo: { type: 'number' }, hi: { type: 'number' }, reasoning: { type: 'string' } },
  required: ['estimate', 'lo', 'hi', 'reasoning'] }
const check = r => ([r.estimate, r.lo, r.hi].every(x => typeof x === 'number' && isFinite(x)) && r.lo <= r.estimate && r.estimate <= r.hi) ? null : 'формат'
const records = []
async function run(c) {
  for (let a = 0; a < 3; a++) {
    let res = null, err = null
    try { res = await agent(c.prompt, { label: a ? `${c.alias}#retry${a}` : c.alias, phase: 'Вызовы', schema: SCHEMA }) } catch (e) { err = String(e) }
    const problem = err || (res == null ? 'пустой ответ' : check(res))
    records.push({ part: args.part, label: c.label, alias: c.alias, attempt: a, retry: a > 0, t: now(), how: 'workflow agent() со схемой', prompt: c.prompt, response: res, problem })
    if (!problem) return
  }
}
await parallel(args.calls.map(c => () => run(c)))
return { part: args.part, records }
