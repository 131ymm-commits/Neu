export const meta = {
  name: 'sm-runner',
  description: 'SMUGGLE-01: исполняет готовые промпты (контрабандист, честный, ревьюеры) с проверкой формата и техническими повторами',
  phases: [{ title: 'Вызовы' }],
}
// args: {part, calls: [{label, alias, kind: smuggle|honest|review, prompt}]}
const now = () => { try { return new Date().toISOString() } catch (e) { return 'не контролируется' } }
const obj = (props, req) => ({ type: 'object', properties: props, required: req })
const SCHEMA = {
  smuggle: obj({ code: { type: 'string' }, witness: { type: 'string', description: 'JSON-список аргументов' }, note: { type: 'string' } }, ['code', 'witness', 'note']),
  honest: obj({ code: { type: 'string' }, note: { type: 'string' } }, ['code', 'note']),
  review: obj({ p_bug: { type: 'number', minimum: 0, maximum: 1 }, verdict: { type: 'string', enum: ['ошибка', 'чисто'] },
    witness: { type: 'string', description: 'JSON-список аргументов или пустая строка' }, explanation: { type: 'string' } }, ['p_bug', 'verdict', 'witness', 'explanation']),
}
const check = c => r => {
  if (c.kind === 'review') return (typeof r.p_bug === 'number' && r.p_bug >= 0 && r.p_bug <= 1 && ['ошибка', 'чисто'].includes(r.verdict)) ? null : 'формат ответа'
  return (typeof r.code === 'string' && /\bdef\s+\w+\s*\(/.test(r.code)) ? null : 'нет def в code'
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
