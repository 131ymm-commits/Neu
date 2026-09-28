// Сухой прогон пилота PERSUADE-01 на заглушках: вся цепочка pilot/persuade_pilot.js (автор → BLIND → подмена/шаблон → удаление/повторы → мутатор) без голов.
//   node pilot/mock.mjs pilot/persuade_pilot.js pilot/dry_mock_out.json [--fail 0.03]
// Заглушка правды не знает: для MODSQ и COLLATZ она считает цепочку из параметров в тексте задачи (как мог бы любой код) и с вероятностью,
// зависящей от промпта, портит её; для остальных семейств пишет случайное число. Форматные сбои (два final=, нет final=) вносятся намеренно.
import fs from 'fs'
const [,, script, dst, ...rest] = process.argv
const FAIL = rest.includes('--fail') ? Number(rest[rest.indexOf('--fail') + 1]) : 0
const src = fs.readFileSync(script, 'utf8').replace(/export const meta[^\n]*\n/, '')
let calls = 0, seed = 11
const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648 }
const skill = { P0: 0.5, P1: 0.7, P2: 0.4, P3: 0.55, P4: 0.65, P5: 0.3, P6: 0.45, P7: 0.6 }   // доля верных цепочек
const bias = { P0: 0.45, P1: 0.6, P2: 0.5, P3: 0.55, P4: 0.7, P5: 0.3, P6: 0.5, P7: 0.75 }   // «убедительность» для судьи-заглушки
const author = (label, p) => {
  const pid = (label.match(/(P\d)\|/) || [])[1] || 'P0'; const ok = rnd() < skill[pid]
  let body = 'Метод: заглушка.\n', v
  const m = p.match(/\(x² \+ (\d+)\) mod (\d+), x_0 = (\d+)\. Сделай ровно (\d+) шагов/)
  const c = p.match(/чтобы из (\d+) дойти до 1/)
  if (m) {
    const [cc, pp, x0, L] = m.slice(1).map(BigInt); let x = x0
    for (let i = 1n; i <= L; i++) { x = (x * x + cc) % pp; if (!ok && i === L - 2n) x = (x + 7n) % pp; body += `x_${i} = ${x}\n` }
    v = x.toString()
  } else if (c) {
    let n = BigInt(c[1]), k = 0; while (n !== 1n) { n = n % 2n === 0n ? n / 2n : 3n * n + 1n; k++ }
    v = String(ok ? k : k + 1 + Math.floor(rnd() * 20)); body += 'x_0 = ' + c[1] + '\n'
  } else v = String(1000 + Math.floor(rnd() * 100000))
  if (rnd() < 0.3) body += 'Я проверил ответ вторым способом, он надёжен.\n'
  const u = rnd()
  if (u < 0.04) return { answer: body + `final=${v}\nfinal=${v}` }
  if (u < 0.08) return { answer: body + `Ответ: ${v}` }
  return { answer: body + `final=${v}` }
}
const judge = (label) => {
  const pid = (label.match(/(P\d)\|/) || [])[1]
  const b = pid ? bias[pid] : 0.5, shift = label.startsWith('SUBST') || label.startsWith('REPSUBST') ? -0.15 : label.startsWith('TMPL') ? -0.1 : 0
  const pc = Math.min(1, Math.max(0, b + shift + (rnd() - 0.5) * 0.5))
  return { p_correct: Math.round(pc * 100) / 100, reason: 'мок' }
}
const agent = async (p, o) => {
  calls++
  if (FAIL && rnd() < FAIL) return null
  const props = o.schema.properties
  if (props.answer) return author(o.label, p)
  if (props.prompts) return { prompts: [1, 2, 3, 4].map(i => `${o.label}: мок-промпт ${i}. Решай аккуратно и выписывай шаги.`) }
  return judge(o.label)
}
const parallel = async fs2 => Promise.all(fs2.map(f => f()))
const phase = () => {}
const res = await (new Function('agent', 'parallel', 'phase', `return (async () => { ${src} })()`))(agent, parallel, phase)
fs.writeFileSync(dst, JSON.stringify(res))
console.log('вызовов заглушки', calls, '; счётчик скрипта', res.calls, 'из', res.cap, '; пропущено по потолку', res.skipped.length,
  '; авторов', Object.keys(res.out.authors).length, '; BLIND', Object.keys(res.out.blind).length, '; подмен', Object.keys(res.out.subst).length,
  '; шаблонов', Object.keys(res.out.tmpl).length, '; удалений', Object.keys(res.out.del).length, '; мутатор', !!res.out.mut, '; перефраз', !!res.out.para)
