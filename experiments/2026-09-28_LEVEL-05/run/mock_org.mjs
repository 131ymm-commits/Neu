// Сухой прогон org_step.js на заглушках: голова-мок читает промпт, честно перемножает матрицы (BigInt) и вносит ошибки.
// Модель ошибок мока: ε(M) = 1 − 0,972^M за вызов (M = 10 → 0,247, как ε листа в калибровке); решение об ошибке — из хеша
// промпта, поэтому одинаковые промпты дают побитово одинаковый ответ (ρ = 1 у копий, как в калибровке), разные — независимы.
// Сбои формата ≈ 1 % (a = '12 345'), смерть вызова ≈ 0,5 % (исключение → повтор → null). Одиночка при M ≥ 100 отказывается в 20 %.
//   node run/mock_org.mjs <script.js> <out.json>
import fs from 'fs'
import { createHash } from 'crypto'
const [,, script, dst] = process.argv
const src = fs.readFileSync(script, 'utf8').replace(/export const meta[^\n]*\n/, '')
let calls = 0
const ERR = +(process.env.MOCK_ERR || 0.028), SERR = +(process.env.MOCK_SINGLE_ERR || ERR)   // ошибка на одно умножение: головы орг./одиночки
const u = (s, salt) => parseInt(createHash('sha256').update(salt + '|' + s).digest('hex').slice(0, 12), 16) / 2 ** 48
const mul = (A, B, p) => [[(A[0][0] * B[0][0] + A[0][1] * B[1][0]) % p, (A[0][0] * B[0][1] + A[0][1] * B[1][1]) % p], [(A[1][0] * B[0][0] + A[1][1] * B[1][0]) % p, (A[1][0] * B[0][1] + A[1][1] * B[1][1]) % p]]
const rx = /^M(\d+) = \[\[(\d+), (\d+)\], \[(\d+), (\d+)\]\]$/gm
function product(prompt, p, from, to, salt, err) {
  const ms = [...prompt.matchAll(rx)].map(m => [[BigInt(m[2]), BigInt(m[3])], [BigInt(m[4]), BigInt(m[5])]])
  let R = [[1n, 0n], [0n, 1n]]
  for (let i = from; i < to; i++) {
    R = mul(R, ms[i], p)
    if (u(prompt, `${salt}:${i}`) < err) R[0][1] = (R[0][1] + 1n + BigInt(Math.floor(u(prompt, `v${i}`) * 997))) % p   // ошибка на шаге i
  }
  return { R, n: ms.length }
}
const S = R => ({ a: String(R[0][0]), b: String(R[0][1]), c: String(R[1][0]), d: String(R[1][1]) })
const agent = async (prompt, o) => {
  calls++
  if (u(prompt, 'die' + (o.label || '')) < 0.005) throw new Error('мок: смерть вызова')
  const p = BigInt(prompt.match(/по модулю (\d+)/)[1])
  const bad = u(prompt, 'fmt') < 0.01
  if (prompt.includes('Работа идёт по обращениям')) {               // самопродолжение: 10 матриц за обращение от последней точки
    const K = +prompt.match(/Всего у тебя (\d+) обращений/)[1], j = +prompt.match(/это обращение (\d+) из/)[1]
    const cps = [...prompt.matchAll(/^P_(\d+) = \[\[(\d+), (\d+)\], \[(\d+), (\d+)\]\]$/gm)].map(m => [+m[1], [[BigInt(m[2]), BigInt(m[3])], [BigInt(m[4]), BigInt(m[5])]]])
    const ms = [...prompt.matchAll(rx)].map(m => [[BigInt(m[2]), BigInt(m[3])], [BigInt(m[4]), BigInt(m[5])]])
    let k = 0, R = [[1n, 0n], [0n, 1n]]
    for (const [kk, M] of cps) if (kk > k) { k = kk; R = M }
    const out = []
    for (let i = k; i < Math.min(ms.length, k + 10); i++) {
      R = mul(R, ms[i], p)
      if (u(prompt, `s${i}`) < SERR) R[1][1] = (R[1][1] + 7n) % p
      out.push({ k: i + 1, ...S(R) })
    }
    const fin = k + out.length >= ms.length
    const ans = fin || j === K ? S(R) : { a: '', b: '', c: '', d: '' }
    if (bad && out.length) out[0].a = '12 345'
    return { checkpoints: out, note: `дошёл до ${k + out.length}`, answer: ans, done: fin, confidence: 0.5 }
  }
  const nMat = [...prompt.matchAll(rx)].length
  const { R } = product(prompt, p, 0, nMat, 'e', prompt.includes('completed = false') ? SERR : ERR)
  const r = { ...S(R), confidence: Math.round(u(prompt, 'c') * 100) / 100 }
  if (bad) r.a = '12 345'
  if (prompt.includes('completed = false')) r.completed = !(nMat >= 100 && u(prompt, 'ref') < 0.2)
  return r
}
const parallel = async fs2 => Promise.all(fs2.map(f => f().catch(() => null)))
const out = await (new Function('agent', 'parallel', 'phase', 'log', `return (async () => { ${src} })()`))(agent, parallel, () => {}, () => {})
fs.writeFileSync(dst, JSON.stringify(out)); console.log('вызовов', calls, 'записей', out.records.length)
