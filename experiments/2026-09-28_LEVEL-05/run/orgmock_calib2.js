export const meta = { name: 'level05-org', description: 'LEVEL-05 организации: вложенное дерево 5→10→20 листьев по 10 матриц 2×2 mod p (без защиты / проверка другим путём), цепочка, одиночка одним вызовом, одиночка с равным бюджетом; калибровка сборки', phases: [{ title: 'Калибровка' }, { title: 'Организации' }, { title: 'Контроли' }] }
// Один сценарий, генотип — в задании (JOBS). Код НЕ считает ответ: только раскладывает матрицы по промптам,
// переставляет элементы (транспонирование) и сравнивает ответы голов по точному равенству.
//   tree   {N, check:'none'|'tr', share?}  — N листьев (по 10 матриц, 1 голова) + N−1 сборок (1 голова: A·B mod p).
//          check 'tr': лист проверяется ДРУГИМ ПУТЁМ — вторая голова считает M10ᵀ·M9ᵀ·…·M1ᵀ (= (M1…M10)ᵀ; промежуточные
//          произведения — суффиксы, а не префиксы; голова не знает, что это транспонирование); код транспонирует обратно
//          и сравнивает. При расхождении решает третий путь — «половины»: (M1…M5) и (M6…M10) двумя вызовами + сборка.
//          Большинство 2 из 3; если все три разные — берётся путь «половины» (флаг unresolved).
//          share: id задания check 'tr' на той же задаче — листья без защиты = первичные вызовы того задания
//          («копия A из того же пула», решение совета 13); своими вызовами идут только сборки.
//   chain  {N}             — N голов по очереди: голова k умножает бегущее произведение на свои 10 матриц.
//   single {N}             — одна голова, один вызов на всех 10·N матрицах; промпт обязывает довести счёт.
//   self   {N, match, K?}  — «одиночка с равным бюджетом»: цепочка вызовов одного промпта, каждый получает свои прошлые
//                             записи (контрольные точки, заметки), K = число вызовов задания match на поддереве N.
//   prod   {from, to, variant:'lr'|'tr'} — калибровка: одно произведение матриц задачи.
const TASKS = {"A0":{"p":345211459,"matrices":[[[21189913,244393585],[78713947,146030850]],[[7274489,189878279],[3356969,237855921]]]},"A1":{"p":160461523,"matrices":[[[101894255,60077283],[46499311,146819604]],[[48775170,110746445],[15926213,51936391]]]},"A2":{"p":990253289,"matrices":[[[612853887,842595826],[20090490,904763498]],[[476446312,14680382],[429467139,813891367]]]},"A3":{"p":549151873,"matrices":[[[4207914,199981117],[466335999,385872192]],[[326960001,497483883],[333378634,437831555]]]},"A4":{"p":742316221,"matrices":[[[125745785,51843134],[73940078,733976501]],[[305503082,450032308],[403041109,710454516]]]},"A5":{"p":642434729,"matrices":[[[538701468,277815077],[55891447,464697553]],[[74890681,59776842],[200860523,247276878]]]},"A6":{"p":939074827,"matrices":[[[547577018,122053675],[214262889,325476639]],[[22029747,654240693],[219031053,799326238]]]},"A7":{"p":335132923,"matrices":[[[157983087,324324679],[238822116,254187377]],[[117214698,161448796],[88357118,14448524]]]},"C10-700":{"p":814574521,"matrices":[[[188,21],[599,293]],[[892,353],[554,420]],[[752,708],[840,384]],[[994,900],[82,263]],[[744,866],[417,137]],[[461,575],[723,392]],[[807,890],[375,678]],[[856,876],[772,534]],[[641,175],[579,482]],[[449,417],[787,542]]]},"C10-701":{"p":584637869,"matrices":[[[15,664],[679,806]],[[267,989],[860,806]],[[537,984],[984,342]],[[230,901],[293,97]],[[357,158],[939,489]],[[238,851],[224,388]],[[407,343],[851,187]],[[572,939],[209,209]],[[620,827],[261,602]],[[920,459],[741,37]]]},"C10-702":{"p":748461979,"matrices":[[[596,368],[945,580]],[[882,112],[19,533]],[[708,120],[561,539]],[[788,767],[161,502]],[[187,384],[855,460]],[[805,283],[271,200]],[[975,872],[814,755]],[[649,619],[645,90]],[[685,106],[699,234]],[[514,810],[268,413]]]},"C10-703":{"p":755589427,"matrices":[[[911,730],[495,327]],[[457,64],[471,44]],[[386,361],[471,55]],[[4,175],[473,808]],[[756,639],[371,698]],[[205,460],[64,246]],[[184,727],[709,900]],[[928,436],[730,732]],[[261,183],[320,722]],[[768,647],[180,248]]]}}   // {id: {p, matrices}}
const JOBS = [{"id":"asm-A0","kind":"prod","task":"A0","from":0,"to":2,"variant":"lr"},{"id":"asm-A1","kind":"prod","task":"A1","from":0,"to":2,"variant":"lr"},{"id":"asm-A2","kind":"prod","task":"A2","from":0,"to":2,"variant":"lr"},{"id":"asm-A3","kind":"prod","task":"A3","from":0,"to":2,"variant":"lr"},{"id":"asm-A4","kind":"prod","task":"A4","from":0,"to":2,"variant":"lr"},{"id":"asm-A5","kind":"prod","task":"A5","from":0,"to":2,"variant":"lr"},{"id":"asm-A6","kind":"prod","task":"A6","from":0,"to":2,"variant":"lr"},{"id":"asm-A7","kind":"prod","task":"A7","from":0,"to":2,"variant":"lr"},{"id":"tr-C10-700","kind":"prod","task":"C10-700","from":0,"to":10,"variant":"tr"},{"id":"tr-C10-701","kind":"prod","task":"C10-701","from":0,"to":10,"variant":"tr"},{"id":"tr-C10-702","kind":"prod","task":"C10-702","from":0,"to":10,"variant":"tr"},{"id":"tr-C10-703","kind":"prod","task":"C10-703","from":0,"to":10,"variant":"tr"}]    // [{id, kind, task, ...}]
const NO = 'Не используй никакие инструменты, не исполняй код и не открывай файлы: считай сам, в уме, опираясь только на текст ниже.'
const MAT = { a: { type: 'string' }, b: { type: 'string' }, c: { type: 'string' }, d: { type: 'string' } }
const CONF = { type: 'number', description: 'вероятность от 0 до 1, что все четыре числа точны' }
const OUT = { type: 'object', properties: { ...MAT, confidence: CONF }, required: ['a', 'b', 'c', 'd', 'confidence'] }
const OUT1 = { type: 'object', properties: { ...MAT, confidence: CONF, completed: { type: 'boolean', description: 'true — счёт доведён до конца; false — не довёл (тогда числа не засчитываются)' } }, required: ['a', 'b', 'c', 'd', 'confidence', 'completed'] }
const OUTS = { type: 'object', properties: {
  checkpoints: { type: 'array', description: 'новые или исправленные контрольные точки этого обращения', items: { type: 'object', properties: { k: { type: 'integer', description: 'сколько первых матриц перемножено' }, ...MAT }, required: ['k', 'a', 'b', 'c', 'd'] } },
  note: { type: 'string', description: 'заметка себе на следующее обращение (план, что перепроверить), 1–3 фразы' },
  answer: { type: 'object', description: 'итог M1·…·Mn mod p; пустые строки, если счёт не закончен', properties: MAT, required: ['a', 'b', 'c', 'd'] },
  done: { type: 'boolean', description: 'true — счёт закончен и перепроверен, дальнейшие обращения не нужны' },
  confidence: CONF }, required: ['checkpoints', 'note', 'answer', 'done', 'confidence'] }

const fmt = m => `[[${m[0][0]}, ${m[0][1]}], [${m[1][0]}, ${m[1][1]}]]`
const T = m => [[m[0][0], m[1][0]], [m[0][1], m[1][1]]]
const hash = s => { let h1 = 0xdeadbeef, h2 = 0x41c6ce57; for (let i = 0; i < s.length; i++) { const c = s.charCodeAt(i); h1 = Math.imul(h1 ^ c, 2654435761); h2 = Math.imul(h2 ^ c, 1597334677) } h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909); h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909); return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16) }
// строгий разбор: только цифры (пробелы по краям допускаются), значение < p; иначе — сбой формата. Ответ не чинится.
function parse(r, p) {
  if (!r) return { fmt: 'null' }
  const xs = [r.a, r.b, r.c, r.d]
  for (const s of xs) {
    if (typeof s !== 'string' || !/^[0-9]+$/.test(s.trim())) return { fmt: 'nonint' }
    if (BigInt(s.trim()) >= BigInt(p)) return { fmt: 'range' }
  }
  const v = xs.map(s => BigInt(s.trim()).toString())
  return { m: [[v[0], v[1]], [v[2], v[3]]], key: v.join(',') }
}
const call = (p, o) => agent(p, o).catch(() => agent(p, o).catch(() => null))
const records = []
const out = {}
function prodPrompt(ms, p) {
  const M = ms.length, tail = M > 2 ? `M1·M2·…·M${M}` : 'M1·M2'
  return `${NO}\n\nПеремножь по порядку ${M} матриц 2×2 по модулю ${p} (после каждого умножения бери остаток по модулю ${p}):\n${ms.map((m, i) => `M${i + 1} = ${fmt(m)}`).join('\n')}\n\nНайди ${tail} mod ${p} = [[a, b], [c, d]]. Верни a, b, c, d и confidence.`
}
// один вызов «перемножь по порядку»; ctx = {job, node, role}; возвращает разобранный результат {m, key} или {fmt}
async function prod(ms, p, ctx, phase) {
  const q = prodPrompt(ms, p), label = `${ctx.job}:${ctx.node}:${ctx.role}`
  const r = await call(q, { label, phase: phase || 'Организации', schema: OUT })
  const x = parse(r, p)
  records.push({ ...ctx, label, n: ms.length, h: hash(q), raw: r, key: x.key || null, fmt: x.fmt || null })
  return x
}
// детерминированные «отложенные» значения для обмена между заданиями (share, match)
const def = {}
const deferred = k => def[k] || (def[k] = (() => { let res; const pr = new Promise(r => { res = r }); return { pr, res } })())

const split = (lo, hi) => lo + Math.floor((hi - lo) / 2)
async function leaf(job, t, i) {
  const ms = t.matrices.slice(10 * i, 10 * i + 10), node = `L${i}`
  const ctx = role => ({ job: job.id, node, role, lo: i, hi: i + 1 })
  if (job.share) {                                               // лист без защиты = первичный вызов задания с проверкой
    const x = await deferred(`${job.share}:P${i}`).pr
    return { ...x, calls: 0, shared: true }
  }
  const pP = prod(ms, t.p, ctx('P'))
  if (job.check === 'tr') {
    pP.then(x => deferred(`${job.id}:P${i}`).res(x))
    const pR = prod(ms.map(T).reverse(), t.p, ctx('TR')).then(x => x.m ? { m: T(x.m), key: T(x.m).flat().join(',') } : x)
    const [P, R] = await Promise.all([pP, pR])
    if (P.key && P.key === R.key) return { ...P, calls: 2, path: 'P=TR' }
    const [H1, H2] = await Promise.all([prod(ms.slice(0, 5), t.p, ctx('H1')), prod(ms.slice(5), t.p, ctx('H2'))])
    let H = { fmt: 'child' }
    if (H1.m && H2.m) H = await prod([H1.m, H2.m], t.p, ctx('HC'))
    const calls = 2 + 2 + (H1.m && H2.m ? 1 : 0)
    if (H.key && H.key === P.key) return { ...P, calls, path: 'P=H' }
    if (H.key && H.key === R.key) return { ...R, calls, path: 'TR=H' }
    return { ...H, calls, path: 'unresolved' }                   // все три разные (или сбои) — берётся путь «половины»
  }
  const P = await pP
  return { ...P, calls: 1, path: 'P' }
}
async function node(job, t, lo, hi, nodes) {
  if (hi - lo === 1) { const x = await leaf(job, t, lo); nodes[`${lo}:${hi}`] = x; return x }
  const m = split(lo, hi)
  const [A, B] = await Promise.all([node(job, t, lo, m, nodes), node(job, t, m, hi, nodes)])
  let x = { fmt: 'child' }, calls = 0
  if (A.m && B.m) { x = await prod([A.m, B.m], t.p, { job: job.id, node: `S${lo}:${hi}`, role: 'A', lo, hi }); calls = 1 }
  nodes[`${lo}:${hi}`] = { ...x, calls }; return nodes[`${lo}:${hi}`]
}
const sub = (nodes, lo, hi) => Object.entries(nodes).filter(([k]) => { const [a, b] = k.split(':').map(Number); return a >= lo && b <= hi }).reduce((s, [, v]) => s + (v.calls || 0), 0)

async function runTree(job, t) {
  const nodes = {}
  const root = await node(job, t, 0, job.N, nodes)
  const calls = sub(nodes, 0, job.N)
  deferred(`${job.id}:calls`).res(Object.fromEntries([5, 10, 20].filter(n => n <= job.N).map(n => [n, sub(nodes, 0, n)])))
  return { key: root.key || null, fmt: root.fmt || null, calls, nodes: Object.fromEntries(Object.entries(nodes).map(([k, v]) => [k, { key: v.key || null, fmt: v.fmt || null, calls: v.calls, path: v.path, shared: v.shared }])) }
}
async function runChain(job, t) {
  let R = null, calls = 0; const links = []
  for (let k = 0; k < job.N; k++) {
    const ms = t.matrices.slice(10 * k, 10 * k + 10)
    const x = await prod(R ? [R, ...ms] : ms, t.p, { job: job.id, node: `C${k}`, role: 'link', lo: k, hi: k + 1 }); calls++
    links.push({ key: x.key || null, fmt: x.fmt || null })
    if (!x.m) return { key: null, fmt: x.fmt, calls, links }
    R = x.m
  }
  return { key: links[links.length - 1].key, fmt: null, calls, links }
}
async function runSingle(job, t) {
  const ms = t.matrices.slice(0, 10 * job.N)
  const q = `${prodPrompt(ms, t.p)}\n\nДоведи счёт до конца, все ${ms.length} умножений: оценка, частичный ответ или отказ не засчитываются. Если всё же не довёл счёт до конца — поставь completed = false.`
  const r = await call(q, { label: `${job.id}:single`, phase: 'Контроли', schema: OUT1 })
  const x = parse(r, t.p)
  const refused = !!r && r.completed === false
  records.push({ job: job.id, node: 'single', role: 'single', n: ms.length, h: hash(q), raw: r, key: x.key || null, fmt: x.fmt || null, refused })
  return { key: refused ? null : (x.key || null), fmt: x.fmt || null, refused, calls: 1 }
}
function selfPrompt(ms, p, K, j, cps, notes, ans) {
  const n = ms.length
  const cpt = Object.keys(cps).map(Number).sort((a, b) => a - b).map(k => `P_${k} = ${fmt(cps[k])}`).join('\n') || '— пока нет'
  const nt = notes.length ? notes.map((s, i) => `обращение ${i + 1}: ${s}`).join('\n') : '— пока нет'
  return `${NO}\n\nЗадача: перемножь по порядку ${n} матриц 2×2 по модулю ${p} (после каждого умножения бери остаток по модулю ${p}):\n${ms.map((m, i) => `M${i + 1} = ${fmt(m)}`).join('\n')}\n\nНайди M1·M2·…·M${n} mod ${p}.\n\n` +
    `Работа идёт по обращениям. Всего у тебя ${K} обращений; это обращение ${j} из ${K}. Между обращениями ты ничего не помнишь, кроме своих записей ниже (новой информации нет — только твои прошлые результаты).\n\n` +
    `Твои контрольные точки (P_k = M1·…·Mk mod ${p}):\n${cpt}\n\nТвои заметки:\n${nt}\n\nТвой последний данный ответ: ${ans ? fmt(ans) : '— пока нет'}\n\n` +
    `Что делать: продолжи счёт от последней контрольной точки, которой доверяешь; можно перепроверять прошлые точки (пересчитать отрезок заново или другим порядком) и исправлять их. Верни checkpoints (новые или исправленные точки этого обращения, k — сколько первых матриц перемножено), note (план на следующее обращение), answer (итог — только когда весь счёт закончен; иначе пустые строки), done и confidence.` +
    (j === K ? `\n\nЭто ПОСЛЕДНЕЕ обращение: answer обязателен.` : '')
}
async function runSelf(job, t) {
  let K = job.K
  if (job.match) { const c = await deferred(`${job.match}:calls`).pr; K = c[job.N] || job.K }
  const ms = t.matrices.slice(0, 10 * job.N), cps = {}, notes = [], trace = []
  let ans = null, ansKey = null, calls = 0, fmtFail = 0
  for (let j = 1; j <= K; j++) {
    const q = selfPrompt(ms, t.p, K, j, cps, notes, ans)
    const r = await call(q, { label: `${job.id}:self${j}`, phase: 'Контроли', schema: OUTS }); calls++
    const a = r && r.answer ? parse(r.answer, t.p) : { fmt: 'null' }
    const empty = r && r.answer && [r.answer.a, r.answer.b, r.answer.c, r.answer.d].every(s => typeof s === 'string' && s.trim() === '')
    const cpOut = []
    for (const c of (r && Array.isArray(r.checkpoints) ? r.checkpoints : [])) {
      const x = parse(c, t.p)
      if (x.m && Number.isInteger(c.k) && c.k >= 1 && c.k <= ms.length) { cps[c.k] = x.m; cpOut.push({ k: c.k, key: x.key }) } else { cpOut.push({ k: c && c.k, fmt: x.fmt || 'k' }); fmtFail++ }
    }
    if (!r) fmtFail++
    else if (!empty && !a.m) fmtFail++
    if (a.m) { ans = a.m; ansKey = a.key }
    if (r && typeof r.note === 'string') notes.push(r.note.slice(0, 400))
    trace.push({ j, h: hash(q), checkpoints: cpOut, answer: a.key || null, done: !!(r && r.done), confidence: r && r.confidence })
    records.push({ job: job.id, node: `self${j}`, role: 'self', n: ms.length, h: hash(q), raw: r, key: a.key || null, fmt: r ? (empty ? null : (a.fmt || null)) : 'null' })
    if (r && r.done && a.m) break                                // голова сама решила, что закончила (бюджет — потолок, не обязанность)
  }
  return { key: ansKey, fmt: ansKey ? null : 'noanswer', K, calls, fmt_fail_calls: fmtFail, trace }
}
async function runProd(job, t) {
  const ms = t.matrices.slice(job.from, job.to)
  const x = job.variant === 'tr' ? await prod(ms.map(T).reverse(), t.p, { job: job.id, node: 'cal', role: 'TR' }, 'Калибровка').then(x => x.m ? { m: T(x.m), key: T(x.m).flat().join(',') } : x)
    : await prod(ms, t.p, { job: job.id, node: 'cal', role: 'P' }, 'Калибровка')
  return { key: x.key || null, fmt: x.fmt || null, calls: 1 }
}
const RUN = { tree: runTree, chain: runChain, single: runSingle, self: runSelf, prod: runProd }
await parallel(JOBS.map(j => async () => {
  try { out[j.id] = { ...(await RUN[j.kind](j, TASKS[j.task])), kind: j.kind, task: j.task } }
  catch (e) {                                                    // сбой задания не должен подвесить связанные (share, match)
    out[j.id] = { error: String(e), kind: j.kind, task: j.task }; deferred(`${j.id}:calls`).res({})
    for (let i = 0; i < 20; i++) deferred(`${j.id}:P${i}`).res({ fmt: 'error' })
  }
}))
return { out, records }
