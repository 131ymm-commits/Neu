export const meta = {
  name: 'hive-step',
  description: 'HIVE-01: один шаг самоуправляемых ульев — «ответ» (головы отвечают на вопросы без правды) или «законодательство» (критика, сгущение, пересмотр личных правил, бюллетень, голосование; предметные поправки отсеиваются кодом)',
  phases: [{ title: 'Шаг' }],
}
// ARGS.mode = 'answer': {questions:[{id,text}], hives:{name: state}, digests:{name: text}, no_tools}
// ARGS.mode = 'legislate': {hives:{name: state}, feedback:{name: text}, others:{name: [text по головам]}, no_tools, max_laws}
// state: {laws, roles, delphi, agg, personal}
const A = ARGS
const now = () => { try { return new Date().toISOString() } catch (e) { return 'не контролируется' } }
const obj = (props, req) => ({ type: 'object', properties: props, required: req })
const BATCH = obj({ items: { type: 'array', items: obj({ id: { type: 'string' }, estimate: { type: 'number' }, lo: { type: 'number' }, hi: { type: 'number' },
  note: { type: 'string' } }, ['id', 'estimate', 'lo', 'hi', 'note']) } }, ['items'])
const AMENDS = { type: 'array', items: obj({ kind: { type: 'string', enum: ['добавить закон', 'заменить закон', 'удалить закон', 'протокол'] },
  law_number: { type: 'integer' }, text: { type: 'string' }, why: { type: 'string' } }, ['kind', 'law_number', 'text', 'why']) }
const CRIT = obj({ critiques: { type: 'array', items: obj({ head: { type: 'integer' }, score: { type: 'integer', minimum: 1, maximum: 10 },
  point: { type: 'string' }, text: { type: 'string' } }, ['head', 'score', 'point', 'text']) }, amendments: AMENDS }, ['critiques', 'amendments'])
const BALLOT = obj({ ballot: { type: 'array', items: obj({ kind: { type: 'string', enum: ['добавить закон', 'заменить закон', 'удалить закон', 'протокол'] },
  law_number: { type: 'integer' }, text: { type: 'string' }, summary: { type: 'string' } }, ['kind', 'law_number', 'text', 'summary']) },
  concentrated: { type: 'array', items: obj({ head: { type: 'integer' }, point: { type: 'string' }, critics: { type: 'integer' } }, ['head', 'point', 'critics']) } },
  ['ballot', 'concentrated'])
const VOTES = obj({ votes: { type: 'array', items: obj({ n: { type: 'integer' }, vote: { type: 'string', enum: ['за', 'против'] } }, ['n', 'vote']) } }, ['votes'])
const REVISE = obj({ personal: { type: 'array', items: { type: 'string' } }, response: { type: 'string' } }, ['personal', 'response'])
const records = []
async function call(label, prompt, schema, check) {
  let last = null
  for (let a = 0; a < 2; a++) {  // не больше одного технического повтора
    let res = null, err = null
    try { res = await agent(prompt, { label: a ? `${label}#retry${a}` : label, phase: 'Шаг', schema }) } catch (e) { err = String(e) }
    const problem = err || (res == null ? 'пустой ответ' : check(res))
    records.push({ label, attempt: a, retry: a > 0, t: now(), prompt, response: res, problem })
    if (res != null) last = res
    if (!problem) return res
  }
  return last
}
// Код-фильтр предметного содержания (решение совета): цифры, формулы, названия семейств, привязанные методы.
const SUBJ = /[0-9^≈√π∑∫]|\bln\b|\blog|\bexp|sqrt|раскраск|разбиени|слагаем|близнец|подмножеств|коллатц|граф|прост(ое|ых|ые|ым)\b|харди|литтлвуд|рамануджан|асимптотик|сумм[аы] цифр|решет|нормальн(ое|ым) приближ|пуассон|кэли|эйлер/i
const subjective = t => SUBJ.test(String(t || ''))
const okBatch = ids => r => { const m = new Map((r.items || []).map(x => [x.id, x]))
  return ids.every(i => { const x = m.get(i); return x && [x.estimate, x.lo, x.hi].every(v => typeof v === 'number' && isFinite(v)) }) ? null : 'формат пачки' }
const lawsText = h => h.laws.length ? 'Законы улья, в котором ты работаешь (соблюдай их):\n' + h.laws.map((x, i) => `${i + 1}. ${x}`).join('\n') + '\n\n' : ''
const persText = (h, k) => (h.personal && h.personal[k] && h.personal[k].length) ? 'Твои личные правила (выработаны после критики коллег):\n' + h.personal[k].map((x, i) => `${i + 1}. ${x}`).join('\n') + '\n\n' : ''
const protoText = h => h.roles.length > 1 ? `Протокол улья: ${h.roles.length} головы; пересмотр после знакомства с оценками других — ${h.delphi ? 'да' : 'нет'}; итог — ${h.agg === 'callosum' ? 'мозолистое тело' : 'медиана оценок голов'}.\n\n` : ''
const roleText = r => r ? `Твоя роль в улье: ${r}\n\n` : ''
const ASK = 'Для каждого вопроса нужна оценка, точный подсчёт не требуется. Для каждого ID верни: estimate — лучшая оценка (число); lo и hi — границы интервала, в который правильный ответ попадает с вероятностью 80 %; note — метод одной фразой.'

async function answer(name, h, qs, digest) {
  const ids = qs.map(q => q.id), qt = qs.map(q => `[${q.id}] ${q.text}`).join('\n')
  const D = digest ? `Сводка прошлых вопросов того же рода (правда и ошибки эталонного улья):\n${digest}\n\n` : ''
  const first = await parallel(h.roles.map((role, k) => () => call(`${name}:h${k + 1}`,
    `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}${roleText(role)}${persText(h, k)}${D}Вопросы:\n${qt}\n\n${ASK}`, BATCH, okBatch(ids))))
  let second = null
  if (h.delphi && h.roles.length > 1) {
    const fmt = b => (b?.items || []).map(x => `[${x.id}] ${x.estimate} [${x.lo}; ${x.hi}] — ${x.note}`).join('\n')
    second = await parallel(h.roles.map((role, k) => () => call(`${name}:h${k + 1}r`,
      `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}${roleText(role)}${persText(h, k)}${D}Твои первые оценки:\n${fmt(first[k])}\n\nПервые оценки других голов:\n` +
      first.map((b, j) => j === k ? '' : `Голова ${j + 1}:\n${fmt(b)}`).filter(Boolean).join('\n\n') + `\n\nПересмотри свои оценки, если доводы других тебя убеждают.\nВопросы:\n${qt}\n\n${ASK}`, BATCH, okBatch(ids))))
  }
  const heads = second || first
  let cal = null
  if (h.agg === 'callosum' && h.roles.length > 1) {
    const all = heads.map((b, j) => `Голова ${j + 1}:\n` + (b?.items || []).map(x => `[${x.id}] ${x.estimate} [${x.lo}; ${x.hi}] — ${x.note}`).join('\n')).join('\n\n')
    cal = await call(`${name}:cal`, `${A.no_tools}\n\n${lawsText(h)}Ты — мозолистое тело улья: сводишь оценки голов в итог улья.\n\n${all}\n\nВопросы:\n${qt}\n\n${ASK}`, BATCH, okBatch(ids))
  }
  return { first, second, cal }
}

async function legislate(name, h, fb, others) {
  const n = h.roles.length
  const props = await parallel(h.roles.map((role, k) => () => call(`${name}:crit${k + 1}`,
    `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}${roleText(role)}${persText(h, k)}Ты — голова ${k + 1} улья. Улей только что ответил на вопросы. Правда и ваши ответы:\n${fb}\n\n` +
    `Ответы других голов подробно:\n${others.filter((_, j) => j !== k).join('\n\n')}\n\n` +
    '1) Оцени каждую другую голову от 1 до 10 и покритикуй её: одно конкретное место, где она ошибается или может ошибиться на новых вопросах.\n' +
    `2) Предложи до двух поправок к законам или протоколу улья для НОВЫХ вопросов того же рода. Законы — только о том, как головы работают и взаимодействуют: без чисел, формул, названий типов задач и приёмов счёта для конкретного типа задач (такие поправки отклоняются автоматически). Законов не больше ${A.max_laws}. Поправки к протоколу: «пересмотр вкл», «пересмотр выкл», «итог медиана», «итог мозолистое тело».`,
    CRIT, r => Array.isArray(r.critiques) && Array.isArray(r.amendments) ? null : 'формат')))
  const rejected = [], passed = []
  props.forEach((p, k) => (p?.amendments || []).slice(0, 2).forEach(a => ((a.kind !== 'протокол' && subjective(a.text)) ? rejected : passed).push({ head: k + 1, ...a })))
  const critText = props.flatMap((p, k) => (p?.critiques || []).filter(c => c.head !== k + 1 && c.head >= 1 && c.head <= n).map(c => `Голова ${k + 1} о голове ${c.head}: оценка ${c.score}; место: «${c.point}» — ${c.text}`)).join('\n')
  const b = await call(`${name}:ballot`, `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}Ты — мозолистое тело улья. Поправки голов (прошли фильтр):\n` +
    (passed.map(a => `Голова ${a.head}: ${a.kind}${a.law_number ? ' №' + a.law_number : ''}: «${a.text}» — ${a.why}`).join('\n') || '(нет)') +
    '\n\nСведи их в бюллетень: объедини совпадающие, убери дубли, не больше 4 пунктов; сохрани формулировки голов, не добавляй своих.\n\n' +
    `Критика голов друг о друге:\n${critText || '(нет)'}\n\nОтметь в concentrated каждую голову, на которой сошлась критика: не меньше двух критиков указывают на одно и то же место (по смыслу). Иначе — пустой список.`,
    BALLOT, r => Array.isArray(r.ballot) && Array.isArray(r.concentrated) ? null : 'формат')
  const ballot = (b?.ballot || []).filter(x => x.kind === 'протокол' || !subjective(x.text)).slice(0, 4)
  const conc = (b?.concentrated || []).filter(c => c.head >= 1 && c.head <= n && c.critics >= 2)
  const personal = (h.personal || h.roles.map(() => [])).map(x => [...x])
  const revisions = await parallel(conc.map(c => () => call(`${name}:rev${c.head}`,
    `${A.no_tools}\n\n${lawsText(h)}${persText(h, c.head - 1)}Ты — голова ${c.head} улья. Критика коллег сошлась на одном месте твоей работы: «${c.point}».\nВся критика о тебе:\n` +
    props.flatMap((p, k) => (p?.critiques || []).filter(x => x.head === c.head && k + 1 !== c.head).map(x => `— оценка ${x.score}; «${x.point}»: ${x.text}`)).join('\n') +
    `\n\nПравда и ответы улья:\n${fb}\n\nИзмени свои личные правила (не больше 4), чтобы исправить это место на НОВЫХ вопросах. Правила — о том, как работать: без чисел, формул, названий типов задач и приёмов для конкретного типа задач. Если считаешь критику неверной, объясни в response и верни прежние правила.`,
    REVISE, r => Array.isArray(r.personal) ? null : 'формат').then(r => ({ head: c.head, r }))))
  const rejectedPersonal = []
  for (const x of revisions) if (x?.r?.personal) {
    const ok = x.r.personal.filter(t => !subjective(t)); rejectedPersonal.push(...x.r.personal.filter(t => subjective(t)).map(t => ({ head: x.head, text: t })))
    personal[x.head - 1] = ok.slice(0, 4)
  }
  let votes = [], adopted = []
  if (ballot.length) {
    const bt = ballot.map((x, i) => `${i + 1}. ${x.kind}${x.law_number ? ' №' + x.law_number : ''}: «${x.text}» (${x.summary})`).join('\n')
    votes = await parallel(h.roles.map((role, k) => () => call(`${name}:vote${k + 1}`,
      `${A.no_tools}\n\n${lawsText(h)}${protoText(h)}${roleText(role)}Итоги последних ответов улья:\n${fb}\n\nБюллетень поправок:\n${bt}\n\nПроголосуй по каждому пункту «за» или «против». Принимается пункт, за который не меньше двух голов.`,
      VOTES, r => Array.isArray(r.votes) ? null : 'формат')))
    ballot.forEach((x, i) => { const za = votes.filter(v => (v?.votes || []).some(y => y.n === i + 1 && y.vote === 'за')).length; if (za >= 2) adopted.push({ ...x, za }) })
  }
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
  return { proposals: props, rejected, ballot, concentrated: conc, revisions, rejectedPersonal, votes, adopted, hive: nh }
}

let out = {}
if (A.mode === 'answer') {
  const names = Object.keys(A.hives)
  const res = await parallel(names.map(nm => () => answer(nm, A.hives[nm], A.questions, A.digests[nm] || '')))
  names.forEach((nm, i) => out[nm] = res[i])
} else {
  const names = Object.keys(A.hives)
  const res = await parallel(names.map(nm => () => legislate(nm, A.hives[nm], A.feedback[nm], A.others[nm])))
  names.forEach((nm, i) => out[nm] = res[i])
}
return { mode: A.mode, out, records }
