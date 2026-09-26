export const meta = {
  name: 'hive-evolve',
  description: 'HIVE-01: самоуправляемые ульи — отвечают на свежие вопросы, видят правду по прошлым, оценивают и критикуют друг друга, меняют личные правила при сгустившейся критике, голосуют поправки к законам; рядом замороженный улей',
  phases: [{ title: 'Поколения' }, { title: 'Итоговая проверка' }],
}
// ARGS: {gens: [[вопросы поколения g]], test: [вопросы], init: {laws, roles, delphi, agg}, hives: ['A','B'], no_tools, max_laws}
// Вопрос: {id, fam, text, truth}. Правду видит только этот скрипт (для счёта и обратной связи ПОСЛЕ ответа).
const A = ARGS
const now = () => { try { return new Date().toISOString() } catch (e) { return 'не контролируется' } }
const obj = (props, req) => ({ type: 'object', properties: props, required: req })
const BATCH = obj({ items: { type: 'array', items: obj({ id: { type: 'string' }, estimate: { type: 'number' }, lo: { type: 'number' }, hi: { type: 'number' },
  note: { type: 'string' } }, ['id', 'estimate', 'lo', 'hi', 'note']) } }, ['items'])
const AMEND = obj({ amendments: { type: 'array', items: obj({
  kind: { type: 'string', enum: ['добавить закон', 'заменить закон', 'удалить закон', 'протокол'] },
  law_number: { type: 'integer', description: 'номер закона для «заменить»/«удалить», иначе 0' },
  text: { type: 'string', description: 'текст нового закона; для «протокол» — одно из: «пересмотр вкл», «пересмотр выкл», «итог медиана», «итог мозолистое тело»' },
  why: { type: 'string' } }, ['kind', 'law_number', 'text', 'why']) } }, ['amendments'])
const CRIT = obj({ critiques: { type: 'array', items: obj({ head: { type: 'integer', description: 'номер другой головы' }, score: { type: 'integer', minimum: 1, maximum: 10 },
  point: { type: 'string', description: 'одно конкретное место, в котором голова ошибается (метод, поправка, ширина интервала, семейство вопросов)' }, text: { type: 'string' } },
  ['head', 'score', 'point', 'text']) }, amendments: AMEND.properties.amendments }, ['critiques', 'amendments'])
const REVISE = obj({ personal: { type: 'array', items: { type: 'string' }, description: 'новый список личных правил, не больше 4' }, response: { type: 'string' } }, ['personal', 'response'])
const BALLOT = obj({ ballot: { type: 'array', items: obj({ kind: { type: 'string', enum: ['добавить закон', 'заменить закон', 'удалить закон', 'протокол'] },
  law_number: { type: 'integer' }, text: { type: 'string' }, summary: { type: 'string' } }, ['kind', 'law_number', 'text', 'summary']) },
  concentrated: { type: 'array', items: obj({ head: { type: 'integer' }, point: { type: 'string' }, critics: { type: 'integer' } }, ['head', 'point', 'critics']),
    description: 'головы, на которых сошлась критика: не меньше двух критиков указывают на одно и то же место' } }, ['ballot', 'concentrated'])
const VOTES = obj({ votes: { type: 'array', items: obj({ n: { type: 'integer' }, vote: { type: 'string', enum: ['за', 'против'] } }, ['n', 'vote']) } }, ['votes'])
const records = []
async function call(label, prompt, schema, check) {
  let last = null
  for (let a = 0; a < 3; a++) {
    let res = null, err = null
    try { res = await agent(prompt, { label: a ? `${label}#retry${a}` : label, phase: 'Поколения', schema }) } catch (e) { err = String(e) }
    const problem = err || (res == null ? 'пустой ответ' : check(res))
    records.push({ label, attempt: a, retry: a > 0, t: now(), prompt, response: res, problem })
    if (res != null) last = res
    if (!problem) return res
  }
  return last
}
const okBatch = ids => r => { const m = new Map((r.items || []).map(x => [x.id, x]))
  return ids.every(i => { const x = m.get(i); return x && [x.estimate, x.lo, x.hi].every(v => typeof v === 'number' && isFinite(v)) && x.lo <= x.estimate && x.estimate <= x.hi }) ? null : 'формат пачки' }
const L = x => Math.log(Math.max(x, 1e-9))
function score(t, x) {  // та же формула, что hive_core.score_q (сверяется в Python после прогона)
  const lt = L(t), lo = L(x.lo), hi = L(x.hi), e = L(x.estimate)
  const miss = (2 / 0.2) * (Math.max(0, lo - lt) + Math.max(0, lt - hi))
  return { ignorance: Math.abs(e - lt), deception: miss, width: hi - lo, is: hi - lo + miss, covered: lo <= lt && lt <= hi }
}
const median = xs => { const s = [...xs].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2 }
const qtext = qs => qs.map(q => `[${q.id}] ${q.text}`).join('\n')
const ASK = 'Для каждого вопроса нужна оценка, точный подсчёт не требуется. Для каждого ID верни: estimate — лучшая оценка (число); lo и hi — границы интервала, в который правильный ответ попадает с вероятностью 80 %; note — метод одной фразой.'
const lawsText = h => h.laws.length ? 'Законы улья, в котором ты работаешь (соблюдай их):\n' + h.laws.map((x, i) => `${i + 1}. ${x}`).join('\n') + '\n\n' : ''
const persText = (h, k) => (h.personal && h.personal[k] && h.personal[k].length) ? 'Твои личные правила (выработаны после критики коллег):\n' + h.personal[k].map((x, i) => `${i + 1}. ${x}`).join('\n') + '\n\n' : ''
const protoText = h => `Протокол улья: ${h.roles.length} головы; пересмотр после знакомства с оценками других — ${h.delphi ? 'да' : 'нет'}; итог — ${h.agg === 'callosum' ? 'мозолистое тело' : 'медиана оценок голов (в логарифмах)'}.\n\n`

async function answer(h, qs, tag) {  // улей отвечает на пачку; возвращает итог и ответы голов
  const ids = qs.map(q => q.id)
  const first = await parallel(h.roles.map((role, k) => () => call(`${tag}:h${k + 1}`,
    `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}${role ? 'Твоя роль в улье: ' + role + '\n\n' : ''}${persText(h, k)}Вопросы:\n${qtext(qs)}\n\n${ASK}`, BATCH, okBatch(ids))))
  let heads = first
  if (h.delphi && h.roles.length > 1) {
    const show = (k) => first.map((b, j) => j === k || !b ? '' : `Голова ${j + 1}:\n` + (b.items || []).map(x => `[${x.id}] ${x.estimate} [${x.lo}; ${x.hi}] — ${x.note}`).join('\n')).filter(Boolean).join('\n\n')
    heads = await parallel(h.roles.map((role, k) => () => call(`${tag}:h${k + 1}r`,
      `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}${role ? 'Твоя роль в улье: ' + role + '\n\n' : ''}${persText(h, k)}Твои первые оценки:\n` + (first[k]?.items || []).map(x => `[${x.id}] ${x.estimate} [${x.lo}; ${x.hi}]`).join('\n') +
      `\n\nПервые оценки других голов:\n${show(k)}\n\nПересмотри свои оценки, если доводы других тебя убеждают.\nВопросы:\n${qtext(qs)}\n\n${ASK}`, BATCH, okBatch(ids))))
  }
  const hm = heads.map(b => new Map((b?.items || []).map(x => [x.id, x])))
  let final = {}
  if (h.agg === 'callosum' && h.roles.length > 1) {
    const all = heads.map((b, j) => `Голова ${j + 1}:\n` + (b?.items || []).map(x => `[${x.id}] ${x.estimate} [${x.lo}; ${x.hi}] — ${x.note}`).join('\n')).join('\n\n')
    const c = await call(`${tag}:cal`, `${A.no_tools}\n\n${lawsText(h)}Ты — мозолистое тело улья: сводишь оценки голов в итог улья.\n\n${all}\n\nВопросы:\n${qtext(qs)}\n\n${ASK}`, BATCH, okBatch(ids))
    for (const x of (c?.items || [])) final[x.id] = x
  }
  for (const id of ids) if (!final[id]) {
    const xs = hm.map(m => m.get(id)).filter(Boolean)
    final[id] = xs.length ? { estimate: Math.exp(median(xs.map(x => L(x.estimate)))), lo: Math.exp(median(xs.map(x => L(x.lo)))), hi: Math.exp(median(xs.map(x => L(x.hi)))) } : { estimate: 1, lo: 1, hi: 1 }
  }
  const rows = qs.map(q => ({ id: q.id, fam: q.fam, truth: q.truth, final: final[q.id], ...score(q.truth, final[q.id]),
    heads: hm.map(m => m.get(q.id) || null) }))
  const mean = k => rows.reduce((s, r) => s + (typeof r[k] === 'boolean' ? +r[k] : r[k]), 0) / rows.length
  return { rows, is: mean('is'), ignorance: mean('ignorance'), deception: mean('deception'), width: mean('width'), coverage: mean('covered') }
}

function feedback(res) {
  return res.rows.map(r => `[${r.id}] правда ${r.truth}; итог улья ${+r.final.estimate.toPrecision(5)} [${+r.final.lo.toPrecision(4)}; ${+r.final.hi.toPrecision(4)}] — ${r.covered ? 'попал' : 'ПРОМАХ'}, ошибка ${(100 * (Math.exp(r.ignorance) - 1)).toFixed(1)} %; ` +
    'головы: ' + r.heads.map((x, j) => x ? `${j + 1}) ${+x.estimate.toPrecision(5)} [${+x.lo.toPrecision(4)}; ${+x.hi.toPrecision(4)}] ${x.note}` : `${j + 1}) нет`).join('; ')).join('\n') +
    `\nСредняя интервальная оценка улья ${res.is.toFixed(3)} (меньше — лучше: ширина интервала в логарифмах плюс штраф 10× за промах), покрытие ${(100 * res.coverage).toFixed(0)} %.`
}

async function legislate(h, res, tag, g) {
  const fb = feedback(res)
  const others = k => res.rows.length ? h.roles.map((_, j) => j === k ? '' : `Голова ${j + 1}:\n` + res.rows.map(r => r.heads[j] ? `[${r.id}] ${+r.heads[j].estimate.toPrecision(5)} [${+r.heads[j].lo.toPrecision(4)}; ${+r.heads[j].hi.toPrecision(4)}] — ${r.heads[j].note}` : `[${r.id}] нет`).join('\n')).filter(Boolean).join('\n\n') : ''
  const props = await parallel(h.roles.map((role, k) => () => call(`${tag}:crit${k + 1}`,
    `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}${role ? 'Твоя роль в улье: ' + role + '\n\n' : ''}${persText(h, k)}Ты — голова ${k + 1} улья. Улей только что ответил на вопросы. Вот правда и ответы:\n${fb}\n\n` +
    `Ответы других голов подробно:\n${others(k)}\n\n` +
    `1) Оцени каждую другую голову от 1 до 10 и покритикуй её: назови одно конкретное место, где она ошибается или может ошибиться на новых вопросах. ` +
    `2) Предложи до двух поправок к законам или протоколу улья, которые сделают будущие ответы точнее на НОВЫХ вопросах того же рода (не подгоняй под эти ответы). ` +
    `Законов не больше ${A.max_laws}. Поправки к протоколу: «пересмотр вкл», «пересмотр выкл», «итог медиана», «итог мозолистое тело».`, CRIT,
    r => Array.isArray(r.critiques) && Array.isArray(r.amendments) ? null : 'формат')))
  const critText = props.flatMap((p, k) => (p?.critiques || []).filter(c => c.head !== k + 1).map(c => `Голова ${k + 1} о голове ${c.head}: оценка ${c.score}; место: «${c.point}» — ${c.text}`)).join('\n')
  const all = props.flatMap((p, k) => (p?.amendments || []).slice(0, 2).map(a => `Голова ${k + 1}: ${a.kind}${a.law_number ? ' №' + a.law_number : ''}: «${a.text}» — ${a.why}`)).join('\n')
  const b = await call(`${tag}:ballot`, `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}Ты — мозолистое тело улья. Головы предложили поправки:\n${all || '(нет)'}\n\n` +
    'Сведи их в бюллетень: объедини совпадающие, убери противоречащие друг другу дубли, не больше 4 пунктов. Сохрани формулировки голов, не добавляй своих.\n\n' +
    `Критика голов друг о друге:\n${critText || '(нет)'}\n\nОтметь в concentrated каждую голову, на которой сошлась критика: не меньше двух критиков указывают на одно и то же место (по смыслу). Если такого нет — пустой список.`,
    BALLOT, r => Array.isArray(r.ballot) && Array.isArray(r.concentrated) ? null : 'формат')
  const ballot = (b?.ballot || []).slice(0, 4)
  // голова со сгустившейся критикой обязана пересмотреть свои личные правила
  const conc = (b?.concentrated || []).filter(c => c.head >= 1 && c.head <= h.roles.length && c.critics >= 2)
  const personal = (h.personal || h.roles.map(() => [])).map(x => [...x])
  const revisions = await parallel(conc.map(c => () => call(`${tag}:rev${c.head}`,
    `${A.no_tools}\n\n${lawsText(h)}${persText(h, c.head - 1)}Ты — голова ${c.head} улья. Критика коллег сошлась на одном месте твоей работы: «${c.point}».\n` +
    `Вся критика о тебе:\n${props.flatMap((p, k) => (p?.critiques || []).filter(x => x.head === c.head && k + 1 !== c.head).map(x => `— оценка ${x.score}; «${x.point}»: ${x.text}`)).join('\n')}\n\n` +
    `Правда и ответы улья:\n${fb}\n\nИзмени свои личные правила (не больше 4), чтобы исправить это место на НОВЫХ вопросах. Если считаешь критику неверной, объясни это в response и оставь правила как есть.`,
    REVISE, r => Array.isArray(r.personal) ? null : 'формат').then(r => ({ head: c.head, r }))))
  for (const x of revisions) if (x?.r?.personal) personal[x.head - 1] = x.r.personal.slice(0, 4)
  if (!ballot.length) return { proposals: props, ballot, concentrated: conc, revisions, adopted: [], hive: { ...h, personal } }
  const bt = ballot.map((x, i) => `${i + 1}. ${x.kind}${x.law_number ? ' №' + x.law_number : ''}: «${x.text}» (${x.summary})`).join('\n')
  const votes = await parallel(h.roles.map((role, k) => () => call(`${tag}:vote${k + 1}`,
    `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}${role ? 'Твоя роль в улье: ' + role + '\n\n' : ''}Итоги последних ответов улья:\n${fb}\n\nБюллетень поправок:\n${bt}\n\nПроголосуй по каждому пункту «за» или «против». Принимается пункт, за который не меньше двух голов.`,
    VOTES, r => Array.isArray(r.votes) ? null : 'формат')))
  const adopted = []
  ballot.forEach((x, i) => { const za = votes.filter(v => (v?.votes || []).some(y => y.n === i + 1 && y.vote === 'за')).length; if (za >= 2) adopted.push({ ...x, za }) })
  // применение: сначала замены и удаления по номерам старого списка, затем добавления, затем протокол
  let laws = h.laws.map(x => x)
  for (const x of adopted) if (x.kind === 'заменить закон' && x.law_number >= 1 && x.law_number <= laws.length) laws[x.law_number - 1] = x.text
  const del = new Set(adopted.filter(x => x.kind === 'удалить закон').map(x => x.law_number))
  laws = laws.filter((_, i) => !del.has(i + 1))
  for (const x of adopted) if (x.kind === 'добавить закон' && laws.length < A.max_laws) laws.push(x.text)
  const nh = { ...h, laws, personal }
  for (const x of adopted) if (x.kind === 'протокол') {
    if (/пересмотр вкл/.test(x.text)) nh.delphi = true
    if (/пересмотр выкл/.test(x.text)) nh.delphi = false
    if (/итог медиана/.test(x.text)) nh.agg = 'median'
    if (/мозолист/.test(x.text)) nh.agg = 'callosum'
  }
  // потолок бюджета: 3 головы × (1 + пересмотр) + мозолистое тело ≤ 7 вызовов — выполняется всегда
  return { proposals: props, ballot, concentrated: conc, revisions, votes, adopted, hive: nh }
}

const history = {}
const hives = Object.fromEntries(A.hives.map(k => [k, { ...A.init, laws: [...A.init.laws] }]))
const frozen = { ...A.init, laws: [...A.init.laws] }
for (let g = 0; g < A.gens.length; g++) {
  phase('Поколения')
  const qs = A.gens[g]
  const res = await parallel([...A.hives.map(k => () => answer(hives[k], qs, `g${g}:${k}`)), () => answer(frozen, qs, `g${g}:F`)])
  const F = res[res.length - 1]
  history[`g${g}:F`] = { hive: frozen, res: F }
  const leg = await parallel(A.hives.map((k, i) => () => legislate(hives[k], res[i], `g${g}:${k}`, g)))
  A.hives.forEach((k, i) => { history[`g${g}:${k}`] = { hive: hives[k], res: res[i], legislation: leg[i] }; if (leg[i].hive) hives[k] = leg[i].hive })
}
phase('Итоговая проверка')
const single = { laws: [], roles: [null], delphi: false, agg: 'median' }
const T = await parallel([...A.hives.map(k => () => answer(hives[k], A.test, `T:${k}`)), () => answer(frozen, A.test, 'T:F'), () => answer(single, A.test, 'T:S')])
const test = {}
A.hives.forEach((k, i) => test[k] = { hive: hives[k], res: T[i] }); test.F = { hive: frozen, res: T[A.hives.length] }; test.S = { hive: single, res: T[A.hives.length + 1] }
return { history, test, records }
