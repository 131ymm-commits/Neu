import fs from 'fs'
const src = fs.readFileSync(process.argv[2], 'utf8').replace(/export const meta[^\n]*\n/, '')
let calls = 0
const agent = async (p, o) => { calls++; const c = BigInt(p.match(/x_k² \+ (\d+)/)[1]), P = BigInt(p.match(/mod (\d+)/)[1]); let x = BigInt(p.match(/Начни с (\d+)/)[1]); const m = +p.match(/Сделай точно (\d+)/)[1]
  const vals = []; for (let i = 0; i < m; i++) { x = (x * x + c) % P; if (i === m - 1 && Math.random() < 0.3) x += 1n; vals.push(String(x)) }
  let check = ''; const pm = p.match(/пересчитай один шаг из (\d+)/); if (pm) check = String((BigInt(pm[1]) ** 2n + c) % P)
  return { check, values: vals } }
const parallel = async fs2 => Promise.all(fs2.map(f => f()))
const out = await (new Function('agent', 'parallel', `return (async () => { ${src} })()`))(agent, parallel)
console.log('вызовов', calls, JSON.stringify(out.out))
