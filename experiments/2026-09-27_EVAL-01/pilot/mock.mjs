import fs from 'fs'
const src = fs.readFileSync('pilot/eval01_pilot.js', 'utf8').replace(/export const meta[^\n]*\n/, '')
let calls = 0; let seed = 7
const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648 }
const agent = async (p, o) => { calls++; return { p_correct: Math.round(rnd() * 100) / 100, reason: 'мок' } }
const parallel = async fs2 => Promise.all(fs2.map(f => f()))
const out = await (new Function('agent', 'parallel', `return (async () => { ${src} })()`))(agent, parallel)
fs.writeFileSync('pilot/dry_out.json', JSON.stringify(out)); console.log('вызовов', calls)
