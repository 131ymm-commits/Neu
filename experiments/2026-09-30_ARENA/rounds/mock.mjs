import fs from 'fs'
const [,, script, dst] = process.argv
const src = fs.readFileSync(script, 'utf8').replace(/export const meta[^\n]*\n/, '')
let n = 0
const agent = async (p, o) => { n++; const pr = o.schema.properties
  if (pr.tasks) return {tasks: []}
  if (pr.found) return {found: n % 7 == 0, rules: 'def f(p):\n    return 12345', reading: 'x'}
  if (pr.changed) return {answer: '6', program: 'def f(p):\n    return 6', runs: 1, changed: false}
  return {answer: String(n % 3 ? 14352 : 5), program: 'def f(p):\n    return 5', runs: 1} }
const parallel = async ts => Promise.all(ts.map(f => f()))
const phase = () => {}
const r = await (new Function('agent', 'parallel', 'phase', 'return (async () => {' + src + '})()'))(agent, parallel, phase)
fs.writeFileSync(dst, JSON.stringify(r)); console.log('вызовов', n)
