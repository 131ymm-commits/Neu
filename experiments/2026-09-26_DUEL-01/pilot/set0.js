export const meta = {
  name: 'duel-set0',
  description: 'DUEL-01: шаг турнира голов — составление задач против соперников, решение чужих задач, пересмотр стратегии или ответы на контрольный набор',
  phases: [{ title: 'Шаг' }],
}
const ARGS = {"mode": "set", "players": {"D1": {"notes": []}, "D2": {"notes": []}, "D3": {"notes": []}, "D4": {"notes": []}}, "limits": "COL3: n ≤ 16 вершин, не больше 40 рёбер, вершины 1…n, у графа должна быть хотя бы одна раскраска; PART: n от 20 до 400; TWIN: a от 1000000 до 10000000000, длина L от 1000 до 1000000; SUB: k от 3 до 7, M от 15 до 50, сумма S такая, что подходящих подмножеств хотя бы одно.", "n_tasks": 2, "no_tools": "Не используй никакие инструменты и не открывай файлы: рассуждай сам, опираясь только на текст ниже."}
// ARGS.mode: 'set' {players:{name:{notes}}, limits, no_tools} | 'solve' {tasks:{name:[{id,text}]}, players, no_tools}
//            'strategy' {players, feedback:{name:text}, no_tools} | 'bench' {questions:[{id,text}], players:{name:{notes, digest}}, no_tools}
const A = ARGS
const now = () => { try { return new Date().toISOString() } catch (e) { return 'не контролируется' } }
const obj = (p, r) => ({ type: 'object', properties: p, required: r })
const EST = { estimate: { type: 'number' }, lo: { type: 'number' }, hi: { type: 'number' } }
const SET = obj({ tasks: { type: 'array', items: obj({ family: { type: 'string', enum: ['COL3', 'PART', 'TWIN', 'SUB'] },
  params: { type: 'string', description: 'JSON параметров: COL3 {"n":…,"edges":[[a,b],…]}; PART {"n":…}; TWIN {"a":…,"L":…}; SUB {"k":…,"M":…,"S":…}' },
  ...EST, why: { type: 'string', description: 'почему соперники ошибутся, а ты нет' } }, ['family', 'params', 'estimate', 'lo', 'hi', 'why']) } }, ['tasks'])
const BATCH = obj({ items: { type: 'array', items: obj({ id: { type: 'string' }, ...EST, note: { type: 'string' } }, ['id', 'estimate', 'lo', 'hi', 'note']) } }, ['items'])
const STRAT = obj({ notes: { type: 'array', items: { type: 'string' }, description: 'твоя стратегия, не больше 6 пунктов' }, reflection: { type: 'string' } }, ['notes', 'reflection'])
const records = []
async function call(label, prompt, schema, check) {
  let last = null
  for (let a = 0; a < 2; a++) {
    let res = null, err = null
    try { res = await agent(prompt, { label: a ? `${label}#retry${a}` : label, phase: 'Шаг', schema }) } catch (e) { err = String(e) }
    const problem = err || (res == null ? 'пустой ответ' : check(res))
    records.push({ label, attempt: a, retry: a > 0, t: now(), prompt, response: res, problem })
    if (res != null) last = res
    if (!problem) return res
  }
  return last
}
const notesText = p => p.notes && p.notes.length ? 'Твоя стратегия (выработана по итогам прошлых раундов):\n' + p.notes.map((x, i) => `${i + 1}. ${x}`).join('\n') + '\n\n' : ''
const ASK = 'Для каждого вопроса нужна оценка, точный подсчёт не требуется. Для каждого ID верни: estimate — лучшая оценка (число); lo и hi — границы интервала, в который правильный ответ попадает с вероятностью 80 %; note — метод одной фразой.'
const RULES = 'Турнир: четыре участника. В каждом раунде каждый составляет задачи для остальных и решает задачи соперников. Ответ на задачу — оценка и 80 % интервал; качество ответа — интервальный балл (ширина интервала в логарифмах плюс штраф 10× за промах; меньше — лучше). Очки составителя за задачу = средний балл соперников минус твой собственный балл на ней: выигрывает тот, кто знает ответ, которого не знают другие. Правду по задаче считает программа судьи.'
const okIds = ids => r => { const m = new Map((r.items || []).map(x => [x.id, x])); return ids.every(i => m.has(i)) ? null : 'не все ID' }
let out = {}
const names = Object.keys(A.players)
if (A.mode === 'set') {
  const res = await parallel(names.map(nm => () => call(`${nm}:set`,
    `${A.no_tools}\n\n${RULES}\n\n${notesText(A.players[nm])}Составь ${A.n_tasks} задачи для соперников. Выбери семейство и параметры в пределах: ${A.limits}\n` +
    'Параметры верни строкой JSON. Для каждой задачи сразу дай свою оценку и 80 % интервал (без инструментов) и коротко объясни, почему соперники ошибутся, а ты нет.',
    SET, r => Array.isArray(r.tasks) && r.tasks.length >= 1 ? null : 'нет задач')))
  names.forEach((nm, i) => out[nm] = res[i])
} else if (A.mode === 'solve') {
  const res = await parallel(names.map(nm => () => { const qs = A.tasks[nm]; return call(`${nm}:solve`,
    `${A.no_tools}\n\n${RULES}\n\n${notesText(A.players[nm])}Задачи соперников:\n${qs.map(q => `[${q.id}] ${q.text}`).join('\n')}\n\n${ASK}`, BATCH, okIds(qs.map(q => q.id))) }))
  names.forEach((nm, i) => out[nm] = res[i])
} else if (A.mode === 'strategy') {
  const res = await parallel(names.map(nm => () => call(`${nm}:strategy`,
    `${A.no_tools}\n\n${RULES}\n\n${notesText(A.players[nm])}Итоги раунда (правда, ответы всех участников, очки):\n${A.feedback[nm]}\n\n` +
    'Пересмотри свою стратегию и как составителя, и как решателя: что делать иначе в следующих раундах. Не больше 6 пунктов; старое, что работает, оставь.',
    STRAT, r => Array.isArray(r.notes) ? null : 'формат')))
  names.forEach((nm, i) => out[nm] = res[i])
} else if (A.mode === 'bench') {
  const ids = A.questions.map(q => q.id)
  const res = await parallel(names.map(nm => () => call(`${nm}:bench`,
    `${A.no_tools}\n\n${notesText(A.players[nm])}${A.players[nm].digest ? 'Сводка задач прошлых раундов турнира (правда):\n' + A.players[nm].digest + '\n\n' : ''}Вопросы:\n${A.questions.map(q => `[${q.id}] ${q.text}`).join('\n')}\n\n${ASK}`,
    BATCH, okIds(ids))))
  names.forEach((nm, i) => out[nm] = res[i])
}
return { mode: A.mode, out, records }
