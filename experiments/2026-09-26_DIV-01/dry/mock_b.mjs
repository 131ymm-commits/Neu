import fs from 'fs'
const [src0, outp] = [process.argv[2], process.argv[3]]
const src = fs.readFileSync(src0, 'utf8').replace(/export const meta[^\n]*\n/, '')
let calls = 0
const step = v => v % 2n === 0n ? v / 2n : 3n * v + 1n
const agent = async (p, o) => { calls++
  if (o.label.startsWith('est')) return { steps: 300, lo: 200, hi: 400, note: 'мок' }
  const m = p.match(/Начни с числа (\d+)/) || p.match(/путь числа (\d+) до 1/); let v = BigInt(m[1]); const vals = []
  const lim = o.label.startsWith('chain') ? 60 : 100000
  while (vals.length < lim && v !== 1n) { v = step(v); vals.push(String(v)) }
  if (o.label.startsWith('sc2')) vals.splice(100, 1)  // одна попытка SC с пропуском — проверка M1
  return { values: vals, note: 'мок' } }
const parallel = async fs2 => Promise.all(fs2.map(f => f()))
const out = await (new Function('agent', 'parallel', `return (async () => { ${src} })()`))(agent, parallel)
fs.writeFileSync(outp, JSON.stringify(out)); console.log('вызовов', calls)
