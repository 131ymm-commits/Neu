export const meta = { name: 'level03-pilot', description: 'LEVEL-03 пилот: пять голов договариваются о слове; с вероятностью 0,15 голова сменяется новичком со своим предпочтением; со связью и без', phases: [{ title: 'Связь' }, { title: 'Без связи' }] }
const NO = "Не используй никакие инструменты и не открывай файлы: решай сам, опираясь только на текст ниже."
const N = 5, T = 250, RHO = 0.15
const gen = seed => { let s = seed; return () => { s = (s * 1103515245 + 12345) % 2147483648; return s / 2147483648 } }
const W = ['СИНИЙ', 'ЗЕЛЁНЫЙ']
const CH = { type: 'object', properties: { choice: { type: 'string', enum: W }, note: { type: 'string' } }, required: ['choice', 'note'] }
async function run(coupled, phase, seed) {
  const rnd = gen(seed), x = Array.from({ length: N }, () => W[rnd() < 0.5 ? 0 : 1]), traj = []
  for (let t = 0; t < T; t++) {
    const i = Math.floor(rnd() * N), newbie = rnd() < RHO, pref = W[rnd() < 0.5 ? 0 : 1], ord = rnd() < 0.5 ? W : [W[1], W[0]]
    const q = `Группа из пяти участников договаривается об общем кодовом слове: ${ord[0]} или ${ord[1]}. Правильного ответа нет; выгодно выбирать то же слово, что и большинство группы.`
    const others = coupled ? `Текущие ответы других участников группы: ${x.filter((_, j) => j !== i).join(', ')}.\n` : ''
    const me = newbie ? `Ты только что пришёл в эту группу из другой, где все говорили ${pref}; тебе привычнее ${pref}.\n` : `Твой прежний ответ: ${x[i]}.\n`
    const r = await agent(`${NO}\n\n${q}\n\n${me}${others}\nВыбери слово (choice) и в note одной фразой — почему.`, { label: `${phase}:t${t}:h${i}${newbie ? ':new' : ''}`, phase, schema: CH }).catch(() => null)
    if (r && r.choice) x[i] = r.choice
    traj.push({ t, i, newbie, pref: newbie ? pref : null, first: ord[0], choice: r && r.choice, state: x.filter(v => v === 'СИНИЙ').length })
  }
  return traj
}
const [C, U] = await Promise.all([run(true, 'Связь', 96001), run(false, 'Без связи', 96002)])
return { coupled: C, uncoupled: U }
