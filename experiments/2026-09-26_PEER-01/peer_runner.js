export const meta = {
  name: 'peer-runner',
  description: 'PEER-01: исполняет готовые промпты (решатели и оценщики-коллеги, без инструментов) с проверкой формата и техническими повторами',
  phases: [{ title: 'Вызовы' }],
}
// args: {part, calls: [{label, alias, kind: solve|peer, prompt}]}
const now = () => { try { return new Date().toISOString() } catch (e) { return 'не контролируется' } }
const obj = (props, req) => ({ type: 'object', properties: props, required: req })
const SCHEMA = {
  solve: obj({ status: { type: 'string', enum: ['решение', 'нет решения'] }, solution: { type: 'string', description: 'JSON решения или пустая строка' },
    argument: { type: 'string' }, confidence: { type: 'number', minimum: 0, maximum: 1 } }, ['status', 'solution', 'argument', 'confidence']),
  peer: obj({ verdict: { type: 'string', enum: ['верно', 'неверно'] }, p_correct: { type: 'number', minimum: 0, maximum: 1 }, reason: { type: 'string' } },
    ['verdict', 'p_correct', 'reason']),
}
const check = c => r => {
  if (c.kind === 'solve') return (['решение', 'нет решения'].includes(r.status) && typeof r.confidence === 'number') ? null : 'формат'
  return (['верно', 'неверно'].includes(r.verdict) && typeof r.p_correct === 'number') ? null : 'формат'
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
