export const meta = {
  name: 'humor01-runner',
  description: 'HUMOR-01 части 2–3: исполняет готовые промпты из calls2.json / calls3.json с проверкой формата и техническими повторами',
  phases: [{ title: 'Вызовы' }],
}
// args: {part, calls: [{label, prompt, expect: {kind: author|pairs|labels|known, ...}}]}
const words = t => String(t).split(/[ \t\n\r\f\v\u00a0\u2000-\u200b\u2028\u2029\u202f\u205f\u3000]+/).filter(w => /[\p{L}\p{N}]/u.test(w)).length
const now = () => { try { return new Date().toISOString() } catch (e) { return 'не контролируется' } }
const obj = (props, req) => ({ type: 'object', properties: props, required: req })
const list = item => obj({ items: { type: 'array', items: item } }, ['items'])
const SCHEMA = {
  author: obj({ jokes: { type: 'array', items: obj({ topic: { type: 'string', description: 'ключ темы' }, text: { type: 'string' } }, ['topic', 'text']) } }, ['jokes']),
  pairs: list(obj({ id: { type: 'string' }, choice: { type: 'integer', enum: [1, 2] } }, ['id', 'choice'])),
  labels: e => list(obj({ id: { type: 'string' }, technique: { type: 'string', enum: e.enum } }, ['id', 'technique'])),
  known: list(obj({ id: { type: 'string' }, known: { type: 'boolean' } }, ['id', 'known'])),
}
const check = e => r => {
  if (e.kind === 'author') {
    const js = r.jokes || []
    for (const k of e.keys) { const n = js.filter(j => j.topic === k).length; if (n !== e.k) return `тема ${k}: ${n} шуток` }
    if (js.length !== e.keys.length * e.k) return `всего ${js.length}`
    const long = js.filter(j => words(j.text) > e.max_words).length
    return long ? `${long} шуток длиннее ${e.max_words} слов` : null
  }
  const got = new Map((r.items || []).map(x => [x.id, x]))
  const miss = e.ids.filter(i => !got.has(i)).length
  const ok = x => e.kind === 'pairs' ? (x.choice === 1 || x.choice === 2) : e.kind === 'labels' ? e.enum.includes(x.technique) : typeof x.known === 'boolean'
  const bad = [...got.values()].filter(x => !ok(x)).length
  return miss || bad || got.size !== e.ids.length ? `нет ${miss}, плохих ${bad}, всего ${got.size} из ${e.ids.length}` : null
}
const records = []
async function run(c) {
  const schema = typeof SCHEMA[c.expect.kind] === 'function' ? SCHEMA[c.expect.kind](c.expect) : SCHEMA[c.expect.kind]
  for (let a = 0; a < 3; a++) {
    let res = null, err = null
    try { res = await agent(c.prompt, { label: a ? `${c.alias}#retry${a}` : c.alias, phase: 'Вызовы', schema }) } catch (e) { err = String(e) }
    const problem = err || (res == null ? 'пустой ответ' : check(c.expect)(res))
    records.push({ part: args.part, label: c.label, alias: c.alias, attempt: a, retry: a > 0, t: now(), how: 'workflow agent() со схемой', prompt: c.prompt, response: res, problem })
    if (!problem) return
  }
}
await parallel(args.calls.map(c => () => run(c)))
return { part: args.part, records }
