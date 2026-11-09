// TESTER-01, оценщик: правда — код. Для сессии тестировщика (session.json от mcp_server.js) повторяет каждый сегмент следа
// на мутанте и на чистой копии, считает детекторы банка по снимкам правды и сопоставляет отчёты с багами:
// отчёт засчитан за баг b, если (1) детектор b сработал на мутанте не позже шага отчёта + 1, (2) категория отчёта ∈ b.cat,
// (3) текст отчёта совпал с ключевыми словами b. Один отчёт — не больше одного бага; баг найден, если засчитан хоть один отчёт.
//   node score.js <session.json> <банк.js> <id копии|clean> [--out score.json]
const fs = require('fs'), path = require('path');
const { GameEnv } = require('./env'); const T = require('./bank_tools');
async function replayTruths(file, trace, seed) {
  const e = await GameEnv.open(file, { seed }); const out = [{ step: 0, truth: await T.truth(e), act: null }];
  try {
    for (let i = 0; i < trace.length; i++) {
      const s = trace[i];
      if (s.op === 'observe') { await e.observe(); continue; }
      if (s.op === 'act') { const r = await e.act(s.a); out.push({ step: i + 1, truth: await T.truth(e), act: { ...s.a, label: r.label || null } }); }
    }
  } finally { await e.close(); }
  return out;
}
function fireAll(run, bugs) {   // для каждого бага — шаги следа, на которых сработал детектор
  const res = {}; for (const b of bugs) { const d = T.detectorFn(b.det); res[b.id] = [];
    run.forEach((s, i) => { try { if (d(s.truth, i ? run[i - 1].truth : null, s.act || {}, run.slice(0, i).map(x => x.truth))) res[b.id].push(s.step); } catch (e) { /* детектор не применим к этому снимку */ } }); }
  return res;
}
async function score(sessionFile, bankFile, copyId) {
  const S = JSON.parse(fs.readFileSync(sessionFile, 'utf8')), bank = require(path.resolve(bankFile));
  const copy = [...bank.copies, ...(bank.pilot || [])].find(c => c.id === copyId); const bugs = copy ? copy.bugs : [];   // clean — без багов
  const segs = [];
  for (const seg of S.segments) {
    const m = await replayTruths(S.game, seg.trace, S.seed), c = await replayTruths(bank.clean, seg.trace, S.seed);
    segs.push({ restart: seg.restart, steps: seg.trace.length, fireM: fireAll(m, bugs), fireC: fireAll(c, bugs), errorsM: (m[m.length - 1].truth.errors || []).length, errorsC: (c[c.length - 1].truth.errors || []).length });
  }
  const credited = {}, reports = [];
  for (const [ri, r] of (S.reports || []).entries()) {
    const seg = segs.find(s => s.restart === (r.segment || 0)), text = [r.title, r.object, r.expected, r.actual, r.repro].filter(Boolean).join(' ');
    let match = null;
    for (const b of bugs) {
      if (credited[b.id] !== undefined) continue;
      const exposed = seg && seg.fireM[b.id].some(k => k <= r.step + 1), catOk = b.cat.includes(r.category), kwOk = new RegExp(b.kw, 'i').test(text);
      if (exposed && catOk && kwOk) { match = b.id; credited[b.id] = ri; break; }
    }
    reports.push({ i: ri, step: r.step, segment: r.segment || 0, category: r.category, confidence: r.confidence, title: r.title, match });
  }
  const exposedAny = Object.fromEntries(bugs.map(b => [b.id, segs.some(s => s.fireM[b.id].length > 0)]));
  const cleanFires = Object.fromEntries(bugs.map(b => [b.id, segs.some(s => s.fireC[b.id].length > 0)]));
  return { session: sessionFile, arm: S.arm, copy: copyId, acts: S.acts, restarts: S.restarts, nReports: reports.length,
    bugs: bugs.map(b => ({ id: b.id, found: credited[b.id] !== undefined, exposed: exposedAny[b.id], cleanFire: cleanFires[b.id] })), reports, segs: segs.map(s => ({ restart: s.restart, steps: s.steps, errorsM: s.errorsM, errorsC: s.errorsC })) };
}
module.exports = { score, replayTruths, fireAll };
if (require.main === module) (async () => {
  const [sf, bf, cid] = process.argv.slice(2), o = process.argv.includes('--out') ? process.argv[process.argv.indexOf('--out') + 1] : null;
  const r = await score(sf, bf, cid); const s = JSON.stringify(r, null, 1); if (o) fs.writeFileSync(o, s); console.log(s.slice(0, 3000));
})();
