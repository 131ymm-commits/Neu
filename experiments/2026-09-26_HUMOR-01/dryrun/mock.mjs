// Сухой прогон: исполняет humor01_train.js / humor01_runner.js с заглушкой agent() (случайные, но формально верные ответы).
// node mock.mjs <script.js> <args.json> <out.json> [сбой_каждые_N]
import fs from 'fs'
const [script, argsPath, outPath, failEvery] = process.argv.slice(2)
let src = fs.readFileSync(script, 'utf8').replace(/export const meta = \{[\s\S]*?\n\}\n/, '')
const args = JSON.parse(fs.readFileSync(argsPath, 'utf8'))
let n = 0
const R = () => Math.random()
const joke = () => 'шутка ' + Array.from({ length: 5 + Math.floor(R() * 30) }, () => 'слово').join(' ')
async function agent(prompt, opts) {
  n++
  if (failEvery && n % Number(failEvery) === 0) return null  // имитация сбоя -> технический повтор
  const P = opts.schema.properties
  if (P.jokes) {
    const keys = [...prompt.matchAll(/^\[([TH]\d)\] /gm)].map(m => m[1]).filter((v, i, a) => a.indexOf(v) === i)
    const k = Number((prompt.match(/Напиши по (\d+)/) || prompt.match(/по (\d+) на каждую/))[1])
    return { jokes: keys.flatMap(t => Array.from({ length: k }, () => ({ topic: t, text: joke() }))) }
  }
  if (P.memo) return { memo: ['пункт ' + n, 'ещё пункт'] }
  const ids = [...prompt.matchAll(/(?:^\[|Пара )([a-z2-9]{5})/gm)].map(m => m[1])
  const it = P.items.items.properties
  if (it.score) return { items: ids.map(id => ({ id, score: 1 + Math.floor(R() * 10), critique: 'так себе' })) }
  if (it.choice) return { items: ids.map(id => ({ id, choice: R() < 0.5 ? 1 : 2 })) }
  if (it.technique) return { items: ids.map(id => ({ id, technique: it.technique.enum[Math.floor(R() * it.technique.enum.length)] })) }
  return { items: ids.map(id => ({ id, known: R() < 0.2 })) }
}
const parallel = fs_ => Promise.all(fs_.map(f => f()))
const phase = () => {}
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const out = await new AsyncFunction('agent', 'parallel', 'phase', 'args', src)(agent, parallel, phase, args)
fs.writeFileSync(outPath, JSON.stringify(out))
console.log('вызовов agent():', n, 'записей:', out.records.length, 'повторов:', out.records.filter(r => r.retry).length)
