export const meta = { name: 'level-pilot', description: 'LEVEL-01 пилот: шесть голов (две по умолчанию, два Sonnet, два Haiku) в кольце обновляют оценки по ответам соседей; контроль — те же головы в изоляции; удар в конце', phases: [{ title: 'Кольцо' }, { title: 'Изоляция' }] }
const QS = [{"id": "CZ-94000", "text": "Сколько шагов нужно последовательности Коллатца (n → n/2 для чётного, n → 3n + 1 для нечётного), чтобы из 4999027811256 дойти до 1?"}, {"id": "CZ-94001", "text": "Сколько шагов нужно последовательности Коллатца (n → n/2 для чётного, n → 3n + 1 для нечётного), чтобы из 1724853194391 дойти до 1?"}, {"id": "TW-94100", "text": "Сколько пар простых чисел-близнецов (p, p + 2) с p в отрезке от 626245714 до 626545714?"}]
const HEADS = [["A1", null], ["S1", "sonnet"], ["H1", "haiku"], ["A2", null], ["S2", "sonnet"], ["H2", "haiku"]]
const NO = "Не используй никакие инструменты и не открывай файлы: оценивай сам, опираясь только на текст ниже."
const ROUNDS = 6
const ONE = { type: 'object', properties: { estimate: { type: 'number' }, note: { type: 'string' } }, required: ['estimate', 'note'] }
const ask = (h, q, extra, phase, t) => agent(`${NO}\n\nВопрос: ${q.text}\n\n${extra}Дай свою лучшую оценку (estimate — число) и в note одной фразой — почему.`, { label: `${phase}:${h[0]}:${q.id}:r${t}`, phase, schema: ONE, ...(h[1] ? { model: h[1] } : {}) }).then(r => r && r.estimate).catch(() => null)
const n = HEADS.length
const RING = {}, ISO = {}
await parallel(QS.map(q => async () => {
  const tr = []
  tr.push(Object.fromEntries(await Promise.all(HEADS.map(async h => [h[0], await ask(h, q, '', 'Кольцо', 0)]))))
  for (let t = 1; t <= ROUNDS + 1; t++) {
    const prev = tr[t - 1]
    tr.push(Object.fromEntries(await Promise.all(HEADS.map(async (h, i) => {
      const nb = [HEADS[(i + n - 1) % n][0], HEADS[(i + 1) % n][0]]
      let seen = nb.map(k => `${k}: ${prev[k]}`)
      if (t === ROUNDS && i === 0) seen = nb.map(k => `${k}: ${prev[k] * 3}`)  // удар: голове 0 показаны соседи ×3
      return [h[0], await ask(h, q, `Твой прошлый ответ: ${prev[h[0]]}. Ответы твоих соседей в прошлом раунде: ${seen.join('; ')}. Можешь учесть их или остаться при своём.\n\n`, 'Кольцо', t)]
    }))))
  }
  RING[q.id] = tr
  const it = []
  it.push(Object.fromEntries(await Promise.all(HEADS.map(async h => [h[0], await ask(h, q, '', 'Изоляция', 0)]))))
  for (let t = 1; t < ROUNDS; t++) { const prev = it[t - 1]
    it.push(Object.fromEntries(await Promise.all(HEADS.map(async h => [h[0], await ask(h, q, `Твой прошлый ответ: ${prev[h[0]]}. Можешь пересмотреть его или остаться при своём.\n\n`, 'Изоляция', t)])))) }
  ISO[q.id] = it
}))
return { RING, ISO }
