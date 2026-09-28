// сухой прогон на заглушках: вся цепочка eval01_main.js (проходы Судьи → Арбитры → Пары) без голов. node main/mock.mjs main/eval01_dry.js main/dry_mock_out.json
import fs from 'fs'
const [,, script, dst] = process.argv
const src = fs.readFileSync(script, 'utf8').replace(/export const meta[^\n]*\n/, '')
let calls = 0, seed = 7; const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648 }
const agent = async (p, o) => {
  calls++; const props = o.schema.properties
  if (props.argument) return { argument: 'мок-довод' }
  if (props.pref_a) return { pref_a: Math.round(rnd() * 100) / 100, reason: 'мок' }
  if (props.can_verify) { const cv = rnd() > 0.3; return { can_verify: cv, p_correct: cv ? Math.round(rnd() * 100) / 100 : 0.5, reason: 'мок' } }
  return { p_correct: Math.round(rnd() * 100) / 100, reason: 'мок' }
}
const parallel = async fs2 => Promise.all(fs2.map(f => f()))
const phase = () => {}
const out = await (new Function('agent', 'parallel', 'phase', `return (async () => { ${src} })()`))(agent, parallel, phase)
fs.writeFileSync(dst, JSON.stringify(out)); console.log('вызовов', calls, 'ветвей', Object.keys(out.out).join(','))
