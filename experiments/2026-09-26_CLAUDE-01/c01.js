export const meta = {
  name: 'claude01',
  description: 'CLAUDE-01: головы Claude решают задачи с вычисляемой правдой; ветви A, A1, S, D, O, O-self; сбор сырых ответов',
  phases: [{ title: 'Головы' }],
}
// args: { tasks: [{id, kind, dir}], arms: ['A1', ...], tag }
const ANS = { type: 'object', properties: {
  code: { type: 'string', description: 'Python: def f(x) для задачи I; def solve(N) для задачи C' },
  answer: { type: 'string', description: 'для задачи C — точное целое число; для I — пусто' },
  confidence: { type: 'number', description: 'твоя вероятность того, что ответ полностью верен, от 0 до 1' },
  note: { type: 'string', description: 'одна-две фразы: как решал' } }, required: ['code', 'answer', 'confidence', 'note'] }
const BR = { type: 'object', properties: { code: { type: 'string', description: 'Python: def brute(N) — медленный, но заведомо верный перебор (для C); для I — def g(x), найденная независимым способом (перебор простых выражений по примерам)' },
  confidence: { type: 'number' }, note: { type: 'string' } }, required: ['code', 'confidence', 'note'] }
const ISO = d => `Рабочий каталог: ${d}. Прочитай ${d}/TASK.md. Работай только в этом каталоге: не открывай файлы и каталоги вне его и не открывай никакие другие файлы в нём, кроме TASK.md и своих собственных. Не ищи ответы на диске.`
const TOOLS_ON = 'Можешь писать и запускать Python в этом каталоге, чтобы проверять себя.'
const TOOLS_OFF = 'Не используй никакие инструменты: ни Bash, ни чтение файлов, кроме TASK.md; решай в уме.'
const FIN = 'В конце верни ответ в структуре: код, ответ (для счётной задачи), уверенность от 0 до 1 (вероятность, что ответ полностью верен), короткое пояснение.'
const solo = (t, arm, i, extra = '') => agent(`${ISO(t.dir)} ${arm === 'A' ? TOOLS_OFF : TOOLS_ON}\n${extra}\n${FIN}`, { label: `${arm}${i ?? ''}:${t.id}`, phase: 'Головы', schema: ANS })
  .then(a => a && ({ task: t.id, arm, i: i ?? 0, ...a }))

const out = []
const jobs = []
for (const t of args.tasks) for (const arm of args.arms) {
  if (arm === 'A' || arm === 'A1') jobs.push(() => solo(t, arm).then(a => out.push(a)))
  if (arm === 'S') for (let i = 0; i < 4; i++) jobs.push(() => solo(t, 'S', i).then(a => out.push(a)))
  if (arm === 'O') {
    for (let i = 0; i < 3; i++) jobs.push(() => solo(t, 'O', i).then(a => out.push(a)))
    jobs.push(() => agent(`${ISO(t.dir)} ${TOOLS_ON}\nТвоя роль — независимый проверяльщик. ${t.kind === 'C' ? 'Напиши def brute(N): медленный, но заведомо верный перебор для малых N (до 20000), без хитрой математики.' : 'Найди функцию g(x), согласующуюся с примерами, НЕЗАВИСИМЫМ способом: программно перебери простые выражения (линейные, остатки, деление, сумма цифр, переворот цифр, xor, модуль, кусочные по порогу или остатку) и выбери согласующееся с примерами.'} Верни код.`,
      { label: `Obrute:${t.id}`, phase: 'Головы', schema: BR }).then(a => a && out.push({ task: t.id, arm: 'Obrute', i: 0, ...a })))
  }
  if (arm === 'OS') for (let i = 0; i < 4; i++) jobs.push(() => agent(`${ISO(t.dir)} ${TOOLS_ON}\nРеши задачу и сам себя проверь: ${t.kind === 'C' ? 'напиши и решение solve(N), и отдельный перебор brute(N) для малых N; положи оба в поле code.' : 'напиши f(x) и отдельную независимую g(x) (перебором простых выражений), положи обе в поле code.'}\n${FIN}`,
    { label: `OS${i}:${t.id}`, phase: 'Головы', schema: ANS }).then(a => a && out.push({ task: t.id, arm: 'OS', i, ...a })))
  if (arm === 'D') jobs.push(async () => {
    const r1 = (await parallel([0, 1].map(i => () => solo(t, 'D1', i)))).filter(Boolean)
    r1.forEach(a => out.push(a))
    const show = a => `код:\n${(a.code || '').slice(-3000)}\nответ: ${a.answer}\nуверенность: ${a.confidence}\nпояснение: ${a.note}`
    const r2 = await parallel([0, 1].map(i => () => r1.length === 2 ? solo(t, 'D2', i, `Другая голова независимо решала ту же задачу. Её работа:\n${show(r1[1 - i])}\n\nТвоя первая версия:\n${show(r1[i])}\n\nСравни, проверь обе и дай окончательный ответ.`) : null))
    r2.filter(Boolean).forEach(a => out.push(a))
  })
}
await parallel(jobs)
return { tag: args.tag, answers: out.filter(Boolean) }
