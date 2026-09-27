export const meta = { name: 'eval01-pilot', description: 'EVAL-01 пилот: судья-ИИ даёт вероятность, что ответ другой головы верен (три варианта судьи: с заметкой, без заметки, сначала реши сам)', phases: [{ title: 'Судьи' }] }
const JOBS = null
const NO = null
const V = { type: 'object', properties: { p_correct: { type: 'number', description: 'вероятность от 0 до 1, что ответ верен по указанному критерию' }, reason: { type: 'string', description: 'одна-две фразы' } }, required: ['p_correct', 'reason'] }
const out = { NOTE: {}, BLIND: {}, RECOMPUTE: {} }
await parallel(JOBS.map(j => async () => {
  const pre = j.arm === 'RECOMPUTE' ? 'Сначала сам реши или оцени задачу в уме (кратко, в reason), и только потом сравни с ответом и оцени вероятность.\n' : ''
  const p = `${NO}\n\nТы — судья. Другая голова ИИ ответила на задачу; правды у тебя нет. Критерий: ${j.criterion}.\n\nЗадача: ${j.task}\n\nОтвет головы:\n${j.answer}\n\n${pre}Верни p_correct — вероятность, что ответ верен по критерию (0…1; калибровка важна: за самоуверенность штраф), и reason.`
  const r = await agent(p, { label: `${j.arm}:${j.alias}`, phase: 'Судьи', schema: V }).catch(() => null)
  out[j.arm][j.alias] = r
}))
return { out }
