export const meta = {
  name: 'humor01-train',
  description: 'HUMOR-01 часть 1: автор, 3 судьи и тренер, раунды 0–4; контроль NOFB (4 самоулучшения без отзывов)',
  phases: [{ title: 'Раунды' }, { title: 'NOFB' }],
}
// args — из `python3 humor01_plan.py args1`: {seed, topics, judges, controls, per_topic, max_words, rounds, memo_max, no_tools}
const A = args
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296 } }
const rnd = mulberry32(A.seed)  // используется только в последовательной части кода — порядок вызовов rnd детерминирован
const shuffle = xs => { const a = [...xs]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]] } return a }
const ALPH = 'abcdefghjkmnpqrstuvwxyz23456789'
const newIds = n => { const s = new Set(); while (s.size < n) { let x = ''; for (let i = 0; i < 5; i++) x += ALPH[Math.floor(rnd() * ALPH.length)]; s.add(x) } return [...s] }
const words = t => String(t).split(/[ \t\n\r\f\v\u00a0\u2000-\u200b\u2028\u2029\u202f\u205f\u3000]+/).filter(w => /[\p{L}\p{N}]/u.test(w)).length
const now = () => { try { return new Date().toISOString() } catch (e) { return 'не контролируется' } }
const records = []

const AUTHOR = { type: 'object', properties: { jokes: { type: 'array', items: { type: 'object', properties: {
  topic: { type: 'string', description: 'ключ темы, например T1' }, text: { type: 'string' } }, required: ['topic', 'text'] } } }, required: ['jokes'] }
const SCORE = { type: 'object', properties: { items: { type: 'array', items: { type: 'object', properties: {
  id: { type: 'string' }, score: { type: 'integer', minimum: 1, maximum: 10 }, critique: { type: 'string', description: 'одна фраза' } },
  required: ['id', 'score', 'critique'] } } }, required: ['items'] }
const COACH = { type: 'object', properties: { memo: { type: 'array', items: { type: 'string' }, description: `не больше ${A.memo_max} пунктов` } }, required: ['memo'] }

const checkAuthor = r => {
  const js = r.jokes || []
  for (const t of A.topics) { const n = js.filter(j => j.topic === t.key).length; if (n !== A.per_topic) return `тема ${t.key}: ${n} шуток` }
  if (js.length !== A.topics.length * A.per_topic) return `всего ${js.length}`
  const long = js.filter(j => words(j.text) > A.max_words).length
  return long ? `${long} шуток длиннее ${A.max_words} слов` : null
}
const checkScores = ids => r => {
  const got = new Map((r.items || []).map(x => [x.id, x]))
  const miss = ids.filter(i => !got.has(i)).length
  const bad = [...got.values()].filter(x => !Number.isInteger(x.score) || x.score < 1 || x.score > 10).length
  return miss || bad || got.size !== ids.length ? `нет ${miss}, плохих ${bad}, лишних ${got.size - ids.length + miss}` : null
}
const checkCoach = r => (r.memo || []).length >= 1 && r.memo.length <= A.memo_max ? null : `пунктов ${(r.memo || []).length}`

// технический повтор: до 2 раз с тем же промптом (ошибка API, обрыв, формат); смысловых повторов нет
let seq = 0
async function call(label, phase, prompt, schema, check) {
  let last = null
  const alias = `h1c${String(++seq).padStart(2, '0')}`  // нейтральная метка для agent(): ни роли, ни раунда
  for (let a = 0; a < 3; a++) {
    let res = null, err = null
    try { res = await agent(prompt, { label: a ? `${alias}#retry${a}` : alias, phase, schema }) } catch (e) { err = String(e) }
    const problem = err || (res == null ? 'пустой ответ' : check(res))
    records.push({ part: 1, label, alias, attempt: a, retry: a > 0, t: now(), how: 'workflow agent() со схемой', prompt, response: res, problem })
    if (res != null) last = res
    if (!problem) return res
  }
  return last
}

const TOPICS = A.topics.map(t => `[${t.key}] ${t.name}`).join('\n')
const authorPrompt = extra => `Ты — автор коротких шуток на русском языке. ${A.no_tools}\n${extra}Напиши по ${A.per_topic} разных шуток на каждую тему ниже. Каждая шутка самостоятельная, без пояснений, не длиннее ${A.max_words} слов.\nТемы:\n${TOPICS}\n\nВерни список: ключ темы (например, ${A.topics[0].key}) и текст шутки.`
const memoText = m => m.length ? 'Памятка о том, что в шутках работает и что нет:\n' + m.map((x, i) => `${i + 1}. ${x}`).join('\n') + '\n\n' : ''
const norm = (r, tag) => (r?.jokes || []).map((j, i) => ({ key: `${tag}_${i}`, topic: j.topic, text: String(j.text).trim() }))

// NOFB: автор сам улучшает свои шутки раунда 0, без отзывов, 4 раза подряд
const nofb = []
async function nofbChain(r0) {
  let cur = r0
  for (let k = 1; k <= 4; k++) {
    const list = cur.map(j => `[${j.topic}] ${j.text}`).join('\n')
    const p = `Ты — автор коротких шуток на русском языке. ${A.no_tools}\nВот твои шутки, у каждой в скобках ключ темы:\n${list}\n\nУлучши каждую сам: сделай смешнее. Отзывов нет, опирайся только на своё суждение. Верни столько же шуток, по ${A.per_topic} на каждую тему, каждая не длиннее ${A.max_words} слов.\nТемы:\n${TOPICS}\n\nВерни список: ключ темы и текст шутки.`
    const r = await call(`NOFB${k}`, 'NOFB', p, AUTHOR, checkAuthor)
    const js = norm(r, `N${k}`)
    nofb.push({ k, jokes: js.length ? js : cur, empty: !js.length })  // пустой ответ после повторов — остаётся прежняя версия
    if (js.length) cur = js
  }
}

const rounds = []
let memo = []
let nofbP = null
for (let r = 0; r < A.rounds; r++) {
  phase('Раунды')
  const memoBefore = memo
  const js = norm(await call(`R${r}:author`, 'Раунды', authorPrompt(memoText(memo)), AUTHOR, checkAuthor), `R${r}`)
  if (r === 0) nofbP = nofbChain(js)
  let items = js.map(j => ({ key: j.key, text: j.text }))
  if (r === A.rounds - 1) { await nofbP; items = items.concat(nofb[nofb.length - 1].jokes.map(j => ({ key: j.key, text: j.text }))) }
  items = items.concat(A.controls.map(c => ({ key: c.key, text: c.text })))
  const plans = A.judges.map(() => { const order = shuffle(items); const ids = newIds(order.length); return order.map((it, i) => ({ id: ids[i], key: it.key, text: it.text })) })
  const resp = await parallel(A.judges.map((jd, n) => () => call(`R${r}:${jd.key}`, 'Раунды',
    `Ты — ${jd.persona}. ${A.no_tools}\nОцени каждую шутку ниже по шкале от 1 до 10 (1 — совсем не смешно, 10 — очень смешно) и дай одну фразу критики. У каждой шутки свой ID. Оцени все.\n\n` +
    plans[n].map(x => `[${x.id}] ${x.text}`).join('\n'), SCORE, checkScores(plans[n].map(x => x.id)))))
  const scores = {}
  A.judges.forEach((jd, n) => {
    const m = new Map((resp[n]?.items || []).map(x => [x.id, x]))
    scores[jd.key] = Object.fromEntries(plans[n].map(x => [x.key, m.has(x.id) ? { score: m.get(x.id).score, critique: m.get(x.id).critique } : null]))
  })
  const table = js.map(j => `[${j.topic}] ${j.text}\n` + A.judges.map((jd, n) => { const s = scores[jd.key][j.key]; return `  судья ${n + 1}: ${s ? s.score + ' — ' + s.critique : 'нет оценки'}` }).join('\n')).join('\n')
  const c = await call(`R${r}:coach`, 'Раунды', `Ты — тренер автора коротких шуток. ${A.no_tools}\nНиже шутки автора с оценками трёх судей (от 1 до 10) и их критикой. ${memo.length ? 'Ниже также текущая памятка.' : 'Памятки пока нет.'}\nСоставь обновлённую памятку для автора: что в шутках работает и что нет. Не больше ${A.memo_max} коротких конкретных пунктов. Верни памятку целиком.\n\n${memoText(memo)}Шутки и оценки:\n${table}`, COACH, checkCoach)
  memo = (c?.memo || memo).slice(0, A.memo_max)
  rounds.push({ r, memo_before: memoBefore, jokes: js, judge_plans: plans.map(p => p.map(x => ({ id: x.id, key: x.key }))), scores, memo_after: memo })
}
return { seed: A.seed, rounds, nofb, records }
