import fs from 'fs'
let src = fs.readFileSync(process.argv[2], 'utf8').replace(/export const meta = \{[\s\S]*?\n\}\n/, '')
let n = 0
async function agent(prompt, o) {
  n++
  const P = o.schema.properties
  if (P.items) { const ids = [...prompt.matchAll(/^\[([A-Z0-9]+-\d+)\]/gm)].map(m => m[1]).filter((v, i, a) => a.indexOf(v) === i)
    return { items: ids.map(id => { const e = 10 + Math.random() * 1000; return { id, estimate: e, lo: e * 0.8, hi: e * 1.2, note: 'м' } }) } }
  if (P.critiques) return { critiques: [1,2,3].map(h => ({ head: h, score: 1 + (n % 10), point: 'ширина интервала', text: 't' })), amendments: [{ kind: 'добавить закон', law_number: 0, text: 'закон ' + n, why: 'w' }] }
  if (P.personal) return { personal: ['личное ' + n], response: 'ок' }
  if (P.amendments) return { amendments: [{ kind: 'добавить закон', law_number: 0, text: 'закон ' + n, why: 'потому' }, { kind: 'протокол', law_number: 0, text: Math.random() < .5 ? 'пересмотр вкл' : 'итог мозолистое тело', why: 'x' }] }
  if (P.ballot) return { concentrated: [1, 2, 3].map(h => ({ head: h, point: 'ширина', critics: 2 })), ballot: [{ kind: 'добавить закон', law_number: 0, text: 'закон ' + n, summary: 's' }, { kind: 'протокол', law_number: 0, text: 'пересмотр вкл', summary: 's' }, { kind: 'протокол', law_number: 0, text: 'итог мозолистое тело', summary: 's' }] }
  if (P.votes) return { votes: [1, 2, 3].map(i => ({ n: i, vote: 'за' })) }
}
const parallel = fs_ => Promise.all(fs_.map(f => f()))
const phase = () => {}
const AF = Object.getPrototypeOf(async function () {}).constructor
const out = await new AF('agent', 'parallel', 'phase', src)(agent, parallel, phase)
fs.writeFileSync(process.argv[3], JSON.stringify(out))
console.log('вызовов', n)
