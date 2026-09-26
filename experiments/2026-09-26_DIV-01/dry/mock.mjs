// Сухой прогон DIV-02: agent() заменён кодом — звено считает точно, одиночка возвращает оценку 10,4·ln n.
import fs from 'fs'
const src = fs.readFileSync('run/div02_run.js', 'utf8').replace(/export const meta[^\n]*\n/, '')
let calls = 0
const agent = async (p, o) => { calls++
  if (o.label.startsWith('chain')) { let v = BigInt(p.match(/Начни с числа (\d+)/)[1]), k = 0
    while (k < 60 && v !== 1n) { v = v % 2n === 0n ? v / 2n : 3n * v + 1n; k++ } return { value: String(v), steps_done: k, reached_one: v === 1n } }
  const n = Number(p.match(/числу (\d+)/)[1]); const s = Math.round(10.4 * Math.log(n)); return { steps: s, lo: s - 80, hi: s + 80, done: false, note: 'мок' } }
const parallel = async fs2 => Promise.all(fs2.map(f => f()))
const out = await (new Function('agent', 'parallel', `return (async () => { ${src} })()`))(agent, parallel)
fs.writeFileSync('dry/out.json', JSON.stringify(out)); console.log('вызовов', calls)
