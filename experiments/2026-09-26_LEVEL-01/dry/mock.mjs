import fs from 'fs'
const src = fs.readFileSync('pilot/level_pilot.js', 'utf8').replace(/export const meta[^\n]*\n/, '')
let calls = 0
const agent = async (p, o) => { calls++; const m = p.match(/прошлый ответ: ([0-9.e+]+)/); const nb = [...p.matchAll(/: ([0-9.e+]+)(;|\.)/g)].map(x => +x[1])
  const base = o.model === 'haiku' ? 560 : o.model === 'sonnet' ? 310 : 300
  if (!m) return { estimate: base, note: 'мок' }; const own = +m[1]
  return { estimate: nb.length > 1 ? (own + nb.slice(-2).reduce((a, b) => a + b, 0)) / 3 : own, note: 'мок' } }
const parallel = async fs2 => Promise.all(fs2.map(f => f()))
const out = await (new Function('agent', 'parallel', `return (async () => { ${src} })()`))(agent, parallel)
fs.writeFileSync('dry/out.json', JSON.stringify(out)); console.log('вызовов', calls)
