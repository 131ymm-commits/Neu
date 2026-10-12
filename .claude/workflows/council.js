export const meta = {
  name: 'council',
  description: 'Совет голов-специалистов: формалист, интуит, скептик, инженер и мозолистое тело ведут диалог над задачей; таймер 10 минут',
  whenToUse: 'Проектирование экспериментов, разбор результатов, спорные решения, проверка PREREG в Neu. args: { task, start, context?, proposal?, rounds?, minutes?, decision? } — start: время запуска в секундах unix (date +%s), обязательно; proposal: текст или путь к файлу; если передан decision, совет сразу голосует по нему',
  phases: [
    { title: 'Раунд 1', detail: 'каждая голова предлагает своё' },
    { title: 'Диалог', detail: 'головы отвечают друг другу через мозолистое тело — пока позволяет таймер' },
    { title: 'Синтез', detail: 'мозолистое тело сводит решение и несогласия' },
    { title: 'Голосование', detail: 'четыре головы голосуют; принято при ≥ 3 «за»; иначе переписать и переголосовать (до 2 раз), если позволяет таймер' },
  ],
}

// Устройство — как до упрощения (коммит 3affdc1). Решение автора 12.10.2026, вечер: «всю систему с мозолистым телом
// и остальным оставить, только таймер 10 минут» (journal/DECISIONS.md). Таймер: Date.now() в скриптах workflow
// запрещён, поэтому время сообщают сами агенты (поле t — `date +%s` в конце работы). Перед каждым необязательным
// шагом (следующий раунд диалога, переписывание с переголосованием) скрипт проверяет, что шаг и обязательный хвост
// (синтез и голосование) укладываются до срока. Синтез и первое голосование идут всегда: это итог заседания.

const HEADS = {
  'Левое (формалист)': 'Ты — левое полушарие совета: огромный специалист по статистике, теории измерений, дизайну экспериментов и формальным доказательствам. Ты мыслишь мерами, порогами, мощностью, ложными уровнями, определениями. Требуешь точных формулировок и проверяемых предсказаний.',
  'Правое (интуит)': 'Ты — правое полушарие совета: огромный специалист по эволюционной биологии, нейронауке, иммунологии и истории науки. Ты мыслишь аналогиями, целостными образами, смелыми гипотезами и неожиданными ходами. Ищешь то, что упустили все остальные.',
  'Скептик': 'Ты — скептик совета: огромный специалист по взлому метрик, закону Гудхарта, утечкам данных, p-хакингу и самообману исследователей. Твоя работа — найти, как предложенное может обмануть оценщика или самих исследователей, и предложить защиту.',
  'Инженер': 'Ты — инженер совета: огромный специалист по реализации экспериментов, производительности кода на CPU, воспроизводимости и бюджету вычислений. Ты отвечаешь за то, что реально сделать за часы на одном 4-ядерном процессоре без GPU и с закрытой сетью (только GitHub и PyPI).',
}
const CALLOSUM = 'Ты — мозолистое тело совета: координатор между полушариями и специалистами. Ты не предлагаешь своё, а передаёшь, сталкиваешь и сводишь: находишь согласия, реальные разногласия и вопросы, на которые головы должны ответить друг другу.'

if (!args || !args.task) throw new Error('нужен args.task')
if (!Number.isFinite(Number(args.start))) throw new Error('нужен args.start — время запуска, секунды unix (date +%s): по нему считается таймер')
const task = args.task
const proposal = args.proposal ? `\n\nПРЕДЛОЖЕНИЕ НА РАЗБОРЕ (если это путь к файлу — прочитай файл целиком):\n${args.proposal}` : ''
const context = (args.context || '') + proposal
const rounds = args.rounds || 2
const start = Number(args.start)
const deadline = start + 60 * (args.minutes || 10)
const EST = { r1: 180, round: 180, synth: 90, vote: 100, rewrite: 60 }   // запасные оценки длительности шагов, с
const RULES = `Пиши по-русски, коротко и конкретно, без воды и без украшений. Не выдумывай числа и источники; если опираешься на память, помечай «(п)». Отвечай 150–350 словами. Не открывай журналы текущего прогона workflow (journal.jsonl, agent-*.jsonl) и файлы других голов. Не больше 10 обращений к инструментам. ТАЙМЕР: заседание кончается в ${deadline} (секунды unix; сейчас — команда \`date +%s\`). Если до конца меньше 3 минут — отвечай сразу, без чтения файлов. В поле t верни результат \`date +%s\` в самом конце работы.`
const TEXT = { type: 'object', properties: { text: { type: 'string', description: 'твоя реплика целиком' }, t: { type: 'integer', description: 'date +%s в конце работы' } }, required: ['text', 't'] }
const VOTE = { type: 'object', properties: { vote: { type: 'string', enum: ['за', 'против', 'воздерживаюсь'] }, reason: { type: 'string' },
  required_change: { type: 'string', description: 'что изменить, чтобы голос стал «за» (пусто, если «за»)' }, t: { type: 'integer', description: 'date +%s в конце работы' } },
  required: ['vote', 'reason', 'required_change', 't'] }

let now = start
const timer = { start, deadline, steps: [], skipped: [] }
const tick = (label, results, est) => {   // время по отметкам агентов; разумные значения — от now до now + 1 ч
  const ts = results.filter(Boolean).map(x => Number(x.t)).filter(x => Number.isFinite(x) && x >= now && x <= now + 3600)
  const before = now
  now = ts.length ? Math.max(...ts) : now + est
  timer.steps.push({ step: label, from: before, to: now, by: ts.length ? 'агенты' : 'оценка' })
  return now - before
}
const fits = (seconds) => now + seconds <= deadline
const opts = (label, ph, schema) => ({ label, phase: ph, schema, effort: 'medium' })

const transcript = []
const preset = args.decision
if (!preset) {
  phase('Раунд 1')
  const first = (await parallel(Object.entries(HEADS).map(([name, role]) => () =>
    agent(`${role}\n\nЗАДАЧА СОВЕТА:\n${task}\n\nКОНТЕКСТ:\n${context}\n\nРаунд 1. Дай своё предложение с точки зрения своей специальности. ${RULES}`,
      opts(`r1:${name}`, 'Раунд 1', TEXT)).then(x => x && ({ name, text: x.text, t: x.t }))))).filter(Boolean)
  EST.r1 = tick('раунд 1', first, EST.r1)
  first.forEach(x => transcript.push({ round: 1, speaker: x.name, text: x.text }))

  let last = first
  for (let r = 2; r <= rounds + 1; r++) {
    if (!fits(EST.round + EST.synth + EST.vote)) { timer.skipped.push(`раунд ${r} диалога`); log(`таймер: раунд ${r} диалога пропущен`); break }
    phase('Диалог')
    const brief = await agent(`${CALLOSUM}\n\nЗАДАЧА: ${task}\n\nРеплики раунда ${r - 1}:\n${last.map(x => `### ${x.name}\n${x.text}`).join('\n\n')}\n\nСведи: где согласны, где настоящее разногласие, и для КАЖДОЙ головы задай 1–2 конкретных вопроса или возражения от других голов, на которые она обязана ответить. ${RULES}`,
      opts(`мозолистое тело:${r}`, 'Диалог', TEXT))
    const t0 = now
    tick(`мозолистое тело ${r}`, [brief], 60)
    const briefText = brief ? brief.text : '(сводка не получена)'
    transcript.push({ round: r, speaker: 'Мозолистое тело', text: briefText })
    const replies = (await parallel(Object.entries(HEADS).map(([name, role]) => () =>
      agent(`${role}\n\nЗАДАЧА: ${task}\n\nКОНТЕКСТ:\n${context}\n\nВСЕ РЕПЛИКИ ПРЕДЫДУЩЕГО РАУНДА:\n${last.map(x => `### ${x.name}\n${x.text}`).join('\n\n')}\n\nСВОДКА МОЗОЛИСТОГО ТЕЛА:\n${briefText}\n\nРаунд ${r}. Ответь на вопросы и возражения, адресованные тебе. Прямо скажи, с чем у других согласен и с чем нет, и измени своё предложение, если тебя убедили. ${RULES}`,
        opts(`r${r}:${name}`, 'Диалог', TEXT)).then(x => x && ({ name, text: x.text, t: x.t }))))).filter(Boolean)
    tick(`раунд ${r}`, replies, EST.round - 60)
    EST.round = Math.max(60, now - t0)
    if (replies.length) last = replies
    replies.forEach(x => transcript.push({ round: r, speaker: x.name, text: x.text }))
  }
}

phase('Синтез')
let decision = preset
if (!preset) {
  const s = await agent(`${CALLOSUM}\n\nЗАДАЧА: ${task}\n\nКОНТЕКСТ:\n${context}\n\nПОЛНАЯ СТЕНОГРАММА:\n${transcript.map(x => `## Раунд ${x.round} — ${x.speaker}\n${x.text}`).join('\n\n')}\n\nСведи итог совета: 1) решение (конкретно и исполнимо); 2) что предложила каждая голова и что из этого вошло; 3) оставшиеся несогласия — честно, с именами голов; 4) что проверить первым. Пиши по-русски, коротко, без украшений. Не выдумывай числа. Не больше 5 обращений к инструментам. В поле t верни \`date +%s\` в конце работы.`,
    opts('синтез', 'Синтез', TEXT))
  EST.synth = tick('синтез', [s], EST.synth)
  decision = s ? s.text : '(синтез не получен)'
}

phase('Голосование')
let current = decision, votes = [], status = 'не принято', attempt = 0
while (attempt < 3) {
  attempt++
  const t0 = now
  votes = (await parallel(Object.entries(HEADS).map(([name, role]) => () =>
    agent(`${role}\n\nЗАДАЧА: ${task}\n\nРЕШЕНИЕ СОВЕТА НА ГОЛОСОВАНИИ (попытка ${attempt}):\n${current}\n\nПроголосуй со своей профессиональной позиции: «за», «против» или «воздерживаюсь». Коротко объясни и, если не «за», назови конкретное изменение, при котором проголосуешь «за». По-русски. Не больше 5 обращений к инструментам. В поле t верни \`date +%s\` в конце работы.`,
      opts(`голос ${attempt}:${name}`, 'Голосование', VOTE)).then(v => v && ({ name, ...v }))))).filter(Boolean)
  tick(`голосование ${attempt}`, votes, EST.vote)
  EST.vote = Math.max(45, now - t0)
  const za = votes.filter(v => v.vote === 'за').length
  transcript.push({ round: `голосование ${attempt}`, speaker: 'итог', text: votes.map(v => `${v.name}: ${v.vote} — ${v.reason}${v.required_change ? ' | нужно: ' + v.required_change : ''}`).join('\n') })
  if (votes.length < 4) { status = `сбой: голосов ${votes.length} из 4`; break }
  if (za === votes.length) { status = 'принято единогласно'; break }
  if (za >= 3) { status = `принято большинством (${za} из ${votes.length})`; break }
  status = `не принято (${za} из ${votes.length})`
  if (attempt === 3) break
  if (!fits(EST.rewrite + EST.vote)) { timer.skipped.push(`переписывание и голосование ${attempt + 1}`); log('таймер: переписывание пропущено'); break }
  const w = await agent(`${CALLOSUM}\n\nРешение не набрало большинства (${za} «за» из ${votes.length}). Голоса:\n${votes.map(v => `${v.name}: ${v.vote} — ${v.reason} | нужно: ${v.required_change}`).join('\n')}\n\nПерепиши решение так, чтобы учесть обоснованные требования, не ломая то, за что уже голосовали «за». Верни полный новый текст решения. По-русски, коротко, без выдуманных чисел. Инструменты не нужны. В поле t верни \`date +%s\` в конце работы.\n\nТЕКУЩЕЕ РЕШЕНИЕ:\n${current}`,
    opts(`переписать ${attempt}`, 'Голосование', TEXT))
  EST.rewrite = tick(`переписать ${attempt}`, [w], EST.rewrite)
  if (w && w.text) current = w.text
}
timer.end = now
timer.over_s = Math.max(0, now - deadline)
return { task, transcript, decision: current, status, votes, timer }
