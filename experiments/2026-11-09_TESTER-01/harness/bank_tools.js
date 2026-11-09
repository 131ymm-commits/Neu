// TESTER-01, инструменты банка багов (без секретов): мутант из правок, снимок «правды» для детекторов, эталонные сценарии по подписям кнопок,
// проверка бага: детектор срабатывает на мутанте и молчит на чистой копии. Сам банк (правки, детекторы, ключевые слова) лежит вне git.
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const { GameEnv } = require('./env');
const sha = s => crypto.createHash('sha256').update(s).digest('hex');

function makeMutant(html, patches) {
  let out = html;
  for (const p of patches) {
    const n = out.split(p.find).length - 1;
    if (n !== 1) throw new Error(`правка ${p.id}: строка найдена ${n} раз(а), нужна ровно одна: ${p.find.slice(0, 80)}`);
    out = out.replace(p.find, p.replace);
  }
  return out;
}

// Снимок «правды» в странице (для детекторов оценщика; голове не показывается).
function pageTruth(game) {
  const T = window.__T, top = (document.getElementById('topbar') || {}).innerText || '', all = (document.body.innerText || '').slice(0, 20000);
  const logs = S => (S.log || []).slice(-15).map(e => typeof e === 'string' ? e : String(e && (e.msg != null ? e.msg : e.ru) || JSON.stringify(e)));
  if (game === 'baeckerei') {
    const B = window.BW, S = B.S, c = Math.floor(S.t % 1440);
    return { game, phase: S.phase, t: S.t, day: Math.floor(S.t / 1440), clock: c, money: S.money, lang: S.lang, speed: S.speed, loan: { ...S.loan },
      items: S.items.map(s => ({ uid: s.uid, type: s.type, price: s.price, x: s.x, y: s.y, w: s.w, h: s.h, zone: B.EQUIP[s.type] && B.EQUIP[s.type].zone })),
      workers: S.workers.map(w => ({ name: w.name, role: w.role, shift: w.shift, away: w.away, fired: !!w.fired, from: w.from, to: w.to })), cands: S.cands.length,
      log: logs(S), errors: T.errors.map(e => e.msg), top, all };
  }
  if (game === 'reifenwerk') {
    const R = window.RW, S = R.S, c = Math.floor(S.t % 1440);
    return { game, phase: S.phase, t: S.t, day: Math.floor(S.t / 1440), clock: c, money: S.money, lang: S.lang, speed: S.speed, kfw: { ...S.kfw },
      stations: R.STATIONS.filter(s => s.built).map(s => ({ id: s.id, kind: s.kind, x: s.x, y: s.y, w: s.w, h: s.h, state: s.state, broken: !!s.broken })),
      workers: S.workers.map(w => ({ name: w.name, role: w.role, shift: w.shift, away: w.away, fee: w.fee })), cands: S.cands.length,
      offers: S.offers.length, orders: S.orders.map(o => ({ id: o.id, state: o.state, qty: o.qty, finished: o.finished })), trucks: S.trucks.length, shipped: S.shipped,
      log: logs(S), errors: T.errors.map(e => e.msg), top, all };
  }
  return { game, errors: T.errors.map(e => e.msg), top, all };
}
async function truth(env) { return env.page.evaluate(([f, g]) => eval(f)(g), [`(${pageTruth.toString()})`, env.game]); }

// Эталонный сценарий: шаги {label:'подпись'} | {label, nth} | {map:[x,y]} | {wait:с} | {key} — по подписям, как сделал бы человек.
async function runMacro(file, steps, { seed = 1 } = {}) {
  const e = await GameEnv.open(file, { seed }); const out = [];
  try {
    out.push({ step: 0, truth: await truth(e) });
    for (const st of steps) {
      let a = st, miss = null;
      if (st.label) {
        const o = await e.observe(); const hits = o.controls.filter(c => c.slice(c.indexOf(':') + 1).includes(st.label) && (!st.region || c.split(' ')[1].replace(':', '') === st.region));
        const h = hits[st.nth || 0]; if (!h) { if (st.optional) continue; miss = `нет кнопки «${st.label}»`; } else a = { click: h.split(' ')[0] };
      }
      const r = miss ? { ok: false, error: miss } : await e.act(a);
      out.push({ step: out.length, macro: st, act: { ...a, label: r.label || null }, ok: r.ok, error: r.error, truth: await truth(e) });
    }
  } finally { out.trace = e.trace.slice(); await e.close(); }
  return out;
}
const detectorFn = src => eval(`(${src})`);
module.exports = { makeMutant, pageTruth, truth, runMacro, detectorFn, sha };
