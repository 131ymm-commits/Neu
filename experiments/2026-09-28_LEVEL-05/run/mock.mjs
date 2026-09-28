import fs from 'fs'
const [,, script, dst] = process.argv
const src = fs.readFileSync(script, 'utf8').replace(/export const meta[^\n]*\n/, '')
let calls = 0, seed = 3; const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648 }
const agent = async (p, o) => { calls++; return { answer: String(Math.floor(rnd() * 3000)), confidence: Math.round(rnd() * 100) / 100, reason: 'мок' } }
const parallel = async fs2 => Promise.all(fs2.map(f => f()))
const out = await (new Function('agent', 'parallel', 'phase', `return (async () => { ${src} })()`))(agent, parallel, () => {})
fs.writeFileSync(dst, JSON.stringify(out)); console.log('вызовов', calls)
