export const meta = { name: 'level02-pilot2', description: 'LEVEL-02 пилот: пять голов асинхронно выбирают между двумя ответами, видя выборы других (или не видя — контроль), с редкими частными подсказками', phases: [{ title: 'Связь' }, { title: 'Без связи' }] }
const Q = "Группа из пяти участников договаривается об общем кодовом слове: СИНИЙ или ЗЕЛЁНЫЙ. Правильного ответа нет; выгодно выбирать то же слово, что и большинство группы."
const NO = "Не используй никакие инструменты и не открывай файлы: решай сам, опираясь только на текст ниже."
const N = 5, T = 200, EPS = 0.15, SEED = 95002
let s = SEED; const rnd = () => { s = (s * 1103515245 + 12345) % 2147483648; return s / 2147483648 }
const CH = { type: 'object', properties: { choice: { type: 'string', enum: ['СИНИЙ', 'ЗЕЛЁНЫЙ'] }, note: { type: 'string' } }, required: ['choice', 'note'] }
async function run(coupled, phase) {
  const x = Array.from({ length: N }, () => rnd() < 0.5 ? 'СИНИЙ' : 'ЗЕЛЁНЫЙ'), traj = []
  for (let t = 0; t < T; t++) {
    const i = Math.floor(rnd() * N), hint = rnd() < EPS ? (rnd() < 0.5 ? 'СИНИЙ' : 'ЗЕЛЁНЫЙ') : null
    const others = coupled ? `Текущие ответы других участников группы: ${x.filter((_, j) => j !== i).join(', ')}.\n` : ''
    const h = hint ? `Твой друг вне группы советует слово ${hint}.\n` : ''
    const p = `${NO}\n\nВопрос: ${Q}\n\nТвой прежний ответ: ${x[i]}.\n${others}${h}\nВыбери ответ (choice) и в note одной фразой — почему.`
    const r = await agent(p, { label: `${phase}:t${t}:h${i}`, phase, schema: CH }).catch(() => null)
    if (r && r.choice) x[i] = r.choice
    traj.push({ t, i, hint, choice: r && r.choice, state: x.filter(v => v === 'СИНИЙ').length })
  }
  return traj
}
const [C, U] = await Promise.all([run(true, 'Связь'), run(false, 'Без связи')])
return { coupled: C, uncoupled: U }
