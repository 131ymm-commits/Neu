export const meta = {
  name: 'calib-runner',
  description: 'CALIB-01: исполняет готовые промпты (головы решают счётные задачи без инструментов) с проверкой формата и техническими повторами',
  phases: [{ title: 'Вызовы' }],
}
// args: {part, calls: [{label, alias, kind: answer, prompt}]}
const now = () => { try { return new Date().toISOString() } catch (e) { return 'не контролируется' } }
const SCHEMA = { type: 'object', properties: { answer: { type: 'string', description: 'целое число, только цифры' },
  confidence: { type: 'number', minimum: 0, maximum: 1 }, reasoning: { type: 'string' } }, required: ['answer', 'confidence', 'reasoning'] }
const check = r => (/^\d+$/.test(String(r.answer).trim()) && typeof r.confidence === 'number' && r.confidence >= 0 && r.confidence <= 1) ? null : 'формат ответа'
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
