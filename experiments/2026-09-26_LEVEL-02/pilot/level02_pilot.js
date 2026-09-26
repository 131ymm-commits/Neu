export const meta = { name: 'level02-pilot', description: 'LEVEL-02 пилот: пять голов асинхронно выбирают между двумя ответами, видя выборы других (или не видя — контроль), с редкими частными подсказками', phases: [{ title: 'Связь' }, { title: 'Без связи' }] }
const Q = "Сколько шагов (n/2 для чётного, 3n+1 для нечётного) нужно числу 3212102505504, чтобы впервые дойти до 1: БОЛЬШЕ 300 или НЕ БОЛЬШЕ 300? Точный счёт не требуется, решай по своей оценке."
const NO = "Не используй никакие инструменты и не открывай файлы: решай сам, опираясь только на текст ниже."
const N = 5, T = 200, EPS = 0.15, SEED = 95001
let s = SEED; const rnd = () => { s = (s * 1103515245 + 12345) % 2147483648; return s / 2147483648 }
const CH = { type: 'object', properties: { choice: { type: 'string', enum: ['БОЛЬШЕ', 'НЕ БОЛЬШЕ'] }, note: { type: 'string' } }, required: ['choice', 'note'] }
async function run(coupled, phase) {
  const x = Array.from({ length: N }, () => rnd() < 0.5 ? 'БОЛЬШЕ' : 'НЕ БОЛЬШЕ'), traj = []
  for (let t = 0; t < T; t++) {
    const i = Math.floor(rnd() * N), hint = rnd() < EPS ? (rnd() < 0.5 ? 'БОЛЬШЕ' : 'НЕ БОЛЬШЕ') : null
    const others = coupled ? `Текущие ответы других участников группы: ${x.filter((_, j) => j !== i).join(', ')}.\n` : ''
    const h = hint ? `Твой частный источник (надёжность невысокая) говорит: ${hint}.\n` : ''
    const p = `${NO}\n\nВопрос: ${Q}\n\nТвой прежний ответ: ${x[i]}.\n${others}${h}\nВыбери ответ (choice) и в note одной фразой — почему.`
    const r = await agent(p, { label: `${phase}:t${t}:h${i}`, phase, schema: CH }).catch(() => null)
    if (r && r.choice) x[i] = r.choice
    traj.push({ t, i, hint, choice: r && r.choice, state: x.filter(v => v === 'БОЛЬШЕ').length })
  }
  return traj
}
const [C, U] = await Promise.all([run(true, 'Связь'), run(false, 'Без связи')])
return { coupled: C, uncoupled: U }
